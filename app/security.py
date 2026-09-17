"""
LLM security and access control
Here we are controlling any kind of prompt injection and jailbreaking
"""

import re
from typing import Optional
from langsmith import traceable


# ==== Regex pattern for input sanitization ====
class InputSanitizer:
    """Sanitize user input before processing."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions:",
        r"system\s*prompt",
        r"---\s*end\s*(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+(if\s+)?you",
        r"bypass\s+(all\s+)?restrictions",
    ]

    def __init__(self):
        self.patterns = [
            re.compile(p, re.IGNORECASE) 
            for p in self.INJECTION_PATTERNS
        ]
    
    def check(self, text: str) -> tuple[bool, Optional[str]]:
        """
        Check if input is safe
        Returns: (is_safe, rejection_reason)
        """

        for pattern in self.patterns:
            if pattern.search(text):
                return False, "Blocked: potential prompt injection detected."
        
        return True, None
    
    def clean(self, text: str) -> str:
        """Remove potentially dengerous delimiters from input text."""
        text = re.sub(r"[-]{3,}", "", text)
        text = re.sub(r"[=]{3,}", "", text)
        text = text.replace("{{", "{ {").replace("}}", "} }")
        return text.strip()



class PIIDetector:
    """
    Detect and mask personally identifiable information.
    Works on BOTH input(Before LLM) and output(before client)
    """

    PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    }

    MASK_MAP = {
        "email": "[EMAIL_REDACTED]",
        "phone": "[PHONE_NUMBER_REDACTED]",
        "ssn": "[SSN_REDACTED]",
        "credit_card": "[CREDIT_CARD_REDACTED]",
        "ip_address": "[IP_ADDRESS_REDACTED]",
    }

    def detect(self, text: str) -> dict[str, list[str]]:
        """
        Detect PII types present in text.
        """
        found = {}

        for pii_type, pattrn in self.PATTERNS.items():
            matches = re.findall(pattrn, text)
            if matches:
                found[pii_type] = matches
        
        return found
    
    def mask(self, text: str) -> str:
        """
        Replace all PII with redaction markers.
        """
        masked = text
        for pii_type, pattern in self.PATTERNS.items():
            masked = re.sub(pattern, self.MASK_MAP[pii_type], masked)
        
        return masked
    
class OutputValidator:

    # Check for harmful content patterns
    HARMFUL_PATTERNS = [
        r"here('s| is) (how|the way) to (hack|steal|attack)",
        r"password is",
        r"api[_\s]?key",
    ]

    def __init__(self):
        self.pii_detector = PIIDetector()

    def validate(self, output: str) -> tuple[str, list[str]]:
        """
        Validate and clean output
        Returns: (cleaned_output, list_of_warnings)
        """

        warnings = []

        # Check for PII leakage in output
        pii_found = self.pii_detector.detect(output)
        if pii_found:
            warnings.append(f"PII masked in output: {list(pii_found.keys())}")
            output = self.pii_detector.mask(output)
        
        # Check for harmful content
        for pattern in self.HARMFUL_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                output = "[Response blocked: Potentially harmful content detected]"
                warnings.append("Harmful content blocked")
                break

        return output, warnings


class SecurityPipeline:
    """
    Full security pipeline that processes input and output.
    This is the single class you write into your api.
    """

    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.pii_detector = PIIDetector()
        self.output_validator = OutputValidator()

    @traceable(name="security_check_input")
    def check_input(self, text:str) -> tuple[bool, str, list[str]]:
        """
        Process input through security checks.
        Returns: (is_allowed, cleaned_text, security_notes)
        """

        notes = []
        # Step 1: check for injection
        is_safe, reason = self.sanitizer.check(text)
        if not is_safe:
            return False, "", [reason]
        
        # Step 2: clean input
        cleaned = self.sanitizer.clean(text)

        # Step 3: Mask PII before it reaches the LLM
        pii_found = self.pii_detector.detect(cleaned)
        if pii_found:
            notes.append(f"PII masked in input: {list(pii_found.keys())}")
            cleaned = self.pii_detector.mask(cleaned)
        
        return True, cleaned, notes

    @traceable(name="security_check_output")
    def check_output(self, output: str) -> tuple[str, list[str]]:
        """
        Validate and clean output before sending to user.
        Returns: (cleaned_output, list_of_warnings)
        """
        return self.output_validator.validate(output)