#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Taisue'
__copyright__ = 'Copyright © 2025/05/23, Banyu Tech Ltd.'


from typing import Any, Callable, Dict, List, Union, cast
import difflib
import nltk
import json

from utils.classes import FailResult, PassResult, ValidationResult, ErrorSpan
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine


class DetectPII():
    """Validates that any text does not contain any PII.

    This validator uses Microsoft's Presidio (https://github.com/microsoft/presidio)
    to detect PII in the text. If PII is detected, the validator will fail with a
    programmatic fix that anonymizes the text. Otherwise, the validator will pass.

    **Key Properties**

    | Property                      | Description                             |
    | ----------------------------- | --------------------------------------- |
    | Name for `format` attribute   | `pii`                                   |
    | Supported data types          | `string`                                |
    | Programmatic fix              | Anonymized text with PII filtered out   |

    Args:
        pii_entities (str | List[str], optional): The PII entities to filter. Must be
            one of `pii` or `spi`. Defaults to None. Can also be set in metadata.
    """

    PII_ENTITIES_MAP = {
        "pii": [
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "DATE_TIME",
            "LOCATION",
            "PERSON",
            "URL",
        ],
        "spi": [
            "CREDIT_CARD",
            "CRYPTO",
            "IBAN_CODE",
            "NRP",
            "MEDICAL_LICENSE",
            "US_BANK_NUMBER",
            "US_DRIVER_LICENSE",
            "US_ITIN",
            "US_PASSPORT",
            "US_SSN",
        ],
    }

    def chunking_function(self, chunk: str):
        """
        Use a sentence tokenizer to split the chunk into sentences.

        Because using the tokenizer is expensive, we only use it if there
        is a period present in the chunk.
        """
        # using the sentence tokenizer is expensive
        # we check for a . to avoid wastefully calling the tokenizer
        if "." not in chunk:
            return []
        sentences = nltk.sent_tokenize(chunk)
        if len(sentences) == 0:
            return []
        if len(sentences) == 1:
            sentence = sentences[0].strip()
            # this can still fail if the last chunk ends on the . in an email address
            if sentence[-1] == ".":
                return [sentence, ""]
            else:
                return []

        # return the sentence
        # then the remaining chunks that aren't finished accumulating
        return [sentences[0], "".join(sentences[1:])]

    def __init__(
        self,
        pii_entities: Union[str, List[str], None] = "pii",
        on_fail: Union[Callable[..., Any], None] = None,
        **kwargs,
    ):
        self.pii_entities = pii_entities
        self.pii_analyzer = AnalyzerEngine()
        self.pii_anonymizer = AnonymizerEngine()

    def get_anonymized_text(self, text: str, entities: List[str]) -> str:
        """Analyze and anonymize the text for PII.

        Args:
            text (str): The text to analyze.
            pii_entities (List[str]): The PII entities to filter.

        Returns:
            anonymized_text (str): The anonymized text.
        """
        results = self.pii_analyzer.analyze(text=text, entities=entities, language="en")
        results = cast(List[Any], results)
        anonymized_text = self.pii_anonymizer.anonymize(
            text=text, analyzer_results=results
        ).text
        return anonymized_text

    def validate(self, value: Any, metadata: Dict[str, Any]) -> ValidationResult:
        # Entities to filter passed through metadata take precedence
        pii_entities = metadata.get("pii_entities", self.pii_entities)
        if pii_entities is None:
            raise ValueError(
                "`pii_entities` must be set in order to use the `DetectPII` validator."
                "Add this: `pii_entities=['PERSON', 'PHONE_NUMBER']`"
                "OR pii_entities='pii' or 'spi'"
                "in init or metadata."
            )

        pii_keys = list(self.PII_ENTITIES_MAP.keys())
        # Check that pii_entities is a string OR list of strings
        if isinstance(pii_entities, str):
            # A key to the PII_ENTITIES_MAP
            entities_to_filter = self.PII_ENTITIES_MAP.get(pii_entities, None)
            if entities_to_filter is None:
                raise ValueError(f"`pii_entities` must be one of {pii_keys}")
        elif isinstance(pii_entities, list):
            entities_to_filter = pii_entities
        else:
            raise ValueError(
                f"`pii_entities` must be one of {pii_keys}" " or a list of strings."
            )

        # Analyze the text, and anonymize it if there is PII
        anonymized_text = self._inference_local(
            {"text": value, "entities": entities_to_filter}
        )
        if anonymized_text == value:
            return PassResult()

        # TODO: this should be refactored into a helper method in OSS
        # get character indices of differences between two strings
        differ = difflib.Differ()
        diffs = list(differ.compare(value, anonymized_text))
        start_range = None
        diff_ranges = []
        # needs to be tracked separately
        curr_index_in_original = 0
        for i in range(len(diffs)):
            if start_range is not None and diffs[i][0] != "-":
                diff_ranges.append((start_range, curr_index_in_original))
                start_range = None
            if diffs[i][0] == "-":
                if start_range is None:
                    start_range = curr_index_in_original
            if diffs[i][0] != "+":
                curr_index_in_original += 1

        error_spans = []
        for diff_range in diff_ranges:
            error_spans.append(
                ErrorSpan(
                    start=diff_range[0],
                    end=diff_range[1],
                    reason=f"PII detected in {value[diff_range[0]:diff_range[1]]}",
                )
            )

        # If anonymized value text is different from original value, then there is PII
        error_msg=f"The following text in your response contains PII:\n{value}"
        return FailResult(
            error_message=(error_msg),
            fix_value=anonymized_text,
            error_spans=error_spans
        )

    def _inference_local(self, model_input: Any) -> Any:
        """Local inference method running the PII analyzer and anonymizer locally."""

        results = self.pii_analyzer.analyze(
            text=model_input["text"], entities=model_input["entities"], language="en"
        )
        results = cast(List[Any], results)
        anonymized_text = self.pii_anonymizer.anonymize(
            text=model_input["text"], analyzer_results=results
        ).text
        return anonymized_text

    def _inference_remote(self, model_input: Any) -> Any:
        """Remote inference method for a hosted ML endpoint"""
        request_body = {
            "inputs": [
                {
                    "name": "text",
                    "shape": [1],
                    "data": [model_input["text"]],
                    "datatype": "BYTES"
                },
                {
                    "name": "pii_entities",
                    "shape": [len(model_input["entities"])],
                    "data": model_input["entities"],
                    "datatype": "BYTES"
                }
            ]
        }
        response = self._hub_inference_request(json.dumps(request_body), self.validation_endpoint)
        return response["outputs"][0]["data"][0]