
"""
Semantic element resolver for the CloudQA AI tester.

Resolves natural-language descriptions to live Selenium WebElements
using DOM metadata and weighted semantic matching.
"""

import re
from dataclasses import dataclass
from typing import Any

from selenium.webdriver.remote.webelement import WebElement


class ElementNotFoundError(Exception):
    """Raised when no suitable element can be resolved."""


class AmbiguousElementError(Exception):
    """Raised when multiple elements have similarly strong matches."""


@dataclass
class ElementMatch:
    element: WebElement
    score: float
    description: str
    tag: str
    matched_by: str
    index: int


class LocatorEngine:
    """
    Resolves descriptions such as:
        - customer email input
        - Login button
        - password field
        - country dropdown
        - dashboard heading

    Does not depend on fixed IDs, names, or CSS classes.
    """

    DOM_SCRIPT = """
        const nodes = Array.from(
            document.querySelectorAll(
                'input,button,select,textarea,a,[role],[contenteditable="true"]'
            )
        );

        return nodes.map((el, index) => {
            const text = (el.innerText || el.textContent || '').trim();
            const type = (el.getAttribute('type') || '').toLowerCase();

            const labels = Array.from(el.labels || [])
                .map(label => label.innerText.trim())
                .filter(Boolean);

            const parentText = el.parentElement
                ? (el.parentElement.innerText || '').trim().slice(0, 200)
                : '';

            return {
                index,
                tag: el.tagName.toLowerCase(),
                type,
                role: el.getAttribute('role') || '',
                text: text.slice(0, 200),
                label: labels.join(' '),
                placeholder: el.getAttribute('placeholder') || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                ariaLabelledBy: el.getAttribute('aria-labelledby') || '',
                name: el.getAttribute('name') || '',
                id: el.id || '',
                value: el.value || '',
                title: el.getAttribute('title') || '',
                parentText,
                disabled: el.disabled === true,
                visible: !!(
                    el.offsetWidth ||
                    el.offsetHeight ||
                    el.getClientRects().length
                ),
                outerHTML: el.outerHTML.slice(0, 350)
            };
        });
    """

    # Generic natural-language synonyms.
    SYNONYMS = {
        "email": {"mail", "e-mail", "username"},
        "password": {"passcode", "pwd"},
        "login": {"log", "sign", "signin", "authenticate"},
        "button": {"btn", "submit", "control"},
        "dropdown": {"select", "combobox", "menu"},
        "select": {"dropdown", "combobox"},
        "field": {"input", "textbox", "text"},
        "textbox": {"input", "field"},
        "heading": {"title", "header"},
        "dashboard": {"home", "overview", "account"},
        "customer": {"user", "client"},
        "first": {"given"},
        "last": {"surname", "family"},
        "name": {"fullname"},
    }

    def __init__(
        self,
        browser,
        minimum_score: float = 35,
        ambiguity_margin: float = 8,
    ):
        self.browser = browser
        self.minimum_score = minimum_score
        self.ambiguity_margin = ambiguity_margin

    @property
    def driver(self):
        return self.browser._require_driver()

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def resolve(
        self,
        description: str,
        action: str = "click",
        timeout: int = 10,
    ) -> ElementMatch:
        """
        Resolve a semantic description into a live WebElement.

        Returns ElementMatch containing:
            element
            score
            description
            tag
            matched_by
            index
        """

        if not description or not description.strip():
            raise ValueError("Element description cannot be empty.")

        from selenium.webdriver.support.ui import WebDriverWait

        last_error = None

        def attempt(_driver):
            nonlocal last_error

            try:
                return self._resolve_once(description, action)
            except (ElementNotFoundError, AmbiguousElementError) as exc:
                last_error = exc
                return False

        try:
            return WebDriverWait(
                self.driver,
                timeout,
                poll_frequency=0.4,
            ).until(attempt)

        except Exception as exc:
            if last_error:
                raise last_error from exc

            raise ElementNotFoundError(
                f"Could not resolve '{description}'. "
                f"Browser error: {exc}"
            ) from exc

    def find_candidates(
        self,
        description: str,
        action: str = "click",
    ) -> list[dict[str, Any]]:
        """Return scored candidate elements for debugging."""

        nodes = self._inspect_dom()
        candidates = []

        for node in nodes:
            if not self._eligible(node, action):
                continue

            score, matched_by = self._score(node, description, action)

            candidates.append({
                "index": node["index"],
                "tag": node["tag"],
                "text": node["text"],
                "label": node["label"],
                "placeholder": node["placeholder"],
                "ariaLabel": node["ariaLabel"],
                "score": round(score, 2),
                "matched_by": matched_by,
            })

        return sorted(
            candidates,
            key=lambda item: item["score"],
            reverse=True,
        )

    def print_candidates(
        self,
        description: str,
        action: str = "click",
        limit: int = 10,
    ):
        candidates = self.find_candidates(description, action)

        print(f"\nCandidates for: {description}")

        for candidate in candidates[:limit]:
            print(
                f"  score={candidate['score']:>6} "
                f"tag={candidate['tag']:<10} "
                f"text={candidate['text'][:45]!r} "
                f"matched={candidate['matched_by']}"
            )

    # ---------------------------------------------------------
    # DOM inspection
    # ---------------------------------------------------------

    def _inspect_dom(self) -> list[dict[str, Any]]:
        """
        Inspect the current page on every resolution attempt.

        The same DOM collection order is used when retrieving
        the corresponding WebElement.
        """

        return self.driver.execute_script(self.DOM_SCRIPT)

    def _get_element_by_index(self, index: int) -> WebElement:
        """
        Retrieve the live element from the inspected DOM collection.
        """

        return self.driver.execute_script(
            """
            const nodes = Array.from(
                document.querySelectorAll(
                    'input,button,select,textarea,a,[role],[contenteditable="true"]'
                )
            );

            return nodes[arguments[0]] || null;
            """,
            index,
        )

    # ---------------------------------------------------------
    # Candidate filtering
    # ---------------------------------------------------------

    def _eligible(self, node: dict, action: str) -> bool:
        if not node.get("visible", True):
            return False

        if node.get("disabled", False):
            return False

        tag = node.get("tag", "")
        element_type = node.get("type", "")
        role = node.get("role", "").lower()

        action = action.lower()

        if action in {"type", "fill"}:
            return (
                tag in {"input", "textarea"}
                or role in {"textbox", "searchbox"}
                or node.get("outerHTML", "").find("contenteditable") >= 0
            )

        if action == "select":
            return tag == "select" or role == "combobox"

        if action in {"click", "press_enter"}:
            return (
                tag in {"button", "a"}
                or role in {"button", "link"}
                or (
                    tag == "input"
                    and element_type in {"submit", "button"}
                )
            )

        # Assertions and waits can target broader element types.
        return True

    # ---------------------------------------------------------
    # Semantic scoring
    # ---------------------------------------------------------

    def _score(
        self,
        node: dict,
        description: str,
        action: str,
    ) -> tuple[float, str]:
        query = self._normalize(description)
        query_tokens = self._expand_tokens(query)

        fields = {
            "label": self._normalize(node.get("label", "")),
            "ariaLabel": self._normalize(node.get("ariaLabel", "")),
            "placeholder": self._normalize(node.get("placeholder", "")),
            "text": self._normalize(node.get("text", "")),
            "name": self._normalize(node.get("name", "")),
            "id": self._normalize(node.get("id", "")),
            "title": self._normalize(node.get("title", "")),
            "parentText": self._normalize(node.get("parentText", "")),
            "type": self._normalize(node.get("type", "")),
            "role": self._normalize(node.get("role", "")),
        }

        # Attribute relevance weights.
        weights = {
            "label": 100,
            "ariaLabel": 95,
            "placeholder": 95,
            "text": 85,
            "title": 75,
            "name": 70,
            "id": 65,
            "role": 55,
            "type": 45,
            "parentText": 35,
        }

        best_score = 0.0
        best_field = "none"

        for field, value in fields.items():
            if not value:
                continue

            score = self._text_similarity(
                query,
                query_tokens,
                value,
            ) * weights[field]

            if score > best_score:
                best_score = score
                best_field = field

        # Contextual boosts for action and semantic intent.
        tag = node.get("tag", "")
        element_type = node.get("type", "").lower()
        role = node.get("role", "").lower()

        if action in {"click", "press_enter"}:
            if tag == "button" or role == "button":
                best_score += 8

            if tag == "a" or role == "link":
                best_score += 5

        elif action in {"type", "fill"}:
            if tag in {"input", "textarea"}:
                best_score += 8

            if element_type == "email" and "email" in query_tokens:
                best_score += 20

            if element_type == "password" and "password" in query_tokens:
                best_score += 20

        elif action == "select":
            if tag == "select" or role == "combobox":
                best_score += 12

        # Avoid matching unrelated input types.
        if "password" in query_tokens and element_type != "password":
            best_score -= 25

        if "email" in query_tokens and element_type not in {"email", "text"}:
            best_score -= 10

        return max(0.0, best_score), best_field

    # ---------------------------------------------------------
    # Matching helpers
    # ---------------------------------------------------------

    def _normalize(self, text: str) -> str:
        text = str(text or "").lower()
        text = re.sub(r"[_\-]+", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _expand_tokens(self, text: str) -> set[str]:
        tokens = set(text.split())

        for token in list(tokens):
            tokens.update(self.SYNONYMS.get(token, set()))

        return tokens

    def _text_similarity(
        self,
        query: str,
        query_tokens: set[str],
        candidate: str,
    ) -> float:
        """
        Return semantic similarity from 0 to 1.

        Exact matches score 1.0.
        Partial token overlap receives proportional credit.
        """

        if not query or not candidate:
            return 0.0

        if query == candidate:
            return 1.0

        if query in candidate:
            return 0.92

        candidate_tokens = set(candidate.split())

        if not candidate_tokens:
            return 0.0

        overlap = query_tokens.intersection(candidate_tokens)

        if not overlap:
            return 0.0

        # Precision and recall balance.
        precision = len(overlap) / len(candidate_tokens)
        recall = len(overlap) / max(len(query_tokens), 1)

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        return min(0.90, f1)

    # ---------------------------------------------------------
    # Final resolution
    # ---------------------------------------------------------

    def _resolve_once(
        self,
        description: str,
        action: str,
    ) -> ElementMatch:
        nodes = self._inspect_dom()
        scored = []

        for node in nodes:
            if not self._eligible(node, action):
                continue

            score, matched_by = self._score(
                node,
                description,
                action,
            )

            if score >= self.minimum_score:
                scored.append((score, matched_by, node))

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        if not scored:
            raise ElementNotFoundError(
                f"No element found for '{description}' "
                f"(action={action}). "
                f"Try a more specific description."
            )

        best_score, best_field, best_node = scored[0]

        # Detect multiple similarly ranked candidates.
        if len(scored) > 1:
            second_score, _, second_node = scored[1]

            if (
                best_score - second_score < self.ambiguity_margin
                and best_node["index"] != second_node["index"]
            ):
                raise AmbiguousElementError(
                    f"Ambiguous match for '{description}'. "
                    f"Top candidates: "
                    f"{best_node.get('text') or best_node.get('label')} "
                    f"(score={best_score:.1f}) and "
                    f"{second_node.get('text') or second_node.get('label')} "
                    f"(score={second_score:.1f}). "
                    f"Provide a more specific element description."
                )

        element = self._get_element_by_index(
            best_node["index"]
        )

        if element is None:
            raise ElementNotFoundError(
                "The DOM changed during element resolution. Retrying."
            )

        return ElementMatch(
            element=element,
            score=best_score,
            description=description,
            tag=best_node["tag"],
            matched_by=best_field,
            index=best_node["index"],
        )


# ---------------------------------------------------------
# Standalone diagnostic mode
# ---------------------------------------------------------

if __name__ == "__main__":
    from browser_engine import BrowserEngine

    with BrowserEngine(headless=False) as browser:
        browser.open(
            "https://app.cloudqa.io/home/AutomationPracticeForm"
        )

        locator = LocatorEngine(browser)

        browser.print_snapshot()

        while True:
            description = input(
                "\nDescribe an element (or 'exit'): "
            ).strip()

            if description.lower() == "exit":
                break

            locator.print_candidates(description)

            try:
                match = locator.resolve(description, action="click")

                print("\nBest match:")
                print(f"  Description: {match.description}")
                print(f"  Tag:        {match.tag}")
                print(f"  Score:      {match.score:.2f}")
                print(f"  Matched by: {match.matched_by}")

            except Exception as exc:
                print(f"\nResolution failed: {exc}")
