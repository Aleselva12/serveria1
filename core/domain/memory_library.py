"""Owner-curated library. Cards are retrieved through explicit scope selection."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from core.domain.memory import MemoryConflict
from core.infra.database import db_connection

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,59}$")]
Scope = Annotated[str, StringConstraints(
    pattern=r"^(?:global|[a-z0-9][a-z0-9_-]{0,59}(?:/[a-z0-9][a-z0-9_-]{0,59}){0,2})$",
)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
CardState = Literal["draft", "approved", "archived"]


class Relation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    kind: Literal["relates_to", "depends_on", "contradicts", "supersedes"]


class CardDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description
    content: Content
    kind: Literal["note", "entity", "fact", "decision", "brief"]
    assertion: Literal["user_statement", "observation", "inference"] = "user_statement"
    state: CardState = "draft"
    source_runs: list[UUID] = Field(default_factory=list, max_length=10)
    relations: list[Relation] = Field(default_factory=list, max_length=20)
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def check_document(self):
        if any(value and value.utcoffset() is None for value in (self.valid_from, self.valid_until)):
            raise ValueError("Le date di validità devono includere il fuso orario.")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("La fine della validità deve seguire l'inizio.")
        if self.assertion != "user_statement" and self.state == "approved" and not self.source_runs:
            raise ValueError("Osservazioni e deduzioni approvate richiedono una fonte.")
        if len(set(self.source_runs)) != len(self.source_runs):
            raise ValueError("Le fonti devono essere univoche.")
        if len({(relation.kind, relation.target_id) for relation in self.relations}) != len(self.relations):
            raise ValueError("I collegamenti devono essere univoci.")
        return self


class CardCreate(CardDocument):
    scope: Scope
    slug: Slug


class CardEdit(CardDocument):
    expected_version: int = Field(ge=1)


_CARD_SELECT = """
    SELECT c.id, c.scope, c.slug, v.version, v.document, v.created_at
    FROM memory_cards c JOIN memory_card_versions v
        ON v.card_id = c.id AND v.version = c.current_version
"""
_VALID_NOW = """
    (v.document->>'valid_from' IS NULL OR (v.document->>'valid_from')::timestamptz <= NOW())
    AND (v.document->>'valid_until' IS NULL OR (v.document->>'valid_until')::timestamptz > NOW())
"""


def visible_scopes(scope: str) -> list[str]:
    parts = scope.split("/")
    return list(dict.fromkeys(["global", *("/".join(parts[:end]) for end in range(1, len(parts) + 1))]))


def _validate_references(connection, card_id, scope, document):
    targets = {relation.target_id for relation in document.relations}
    if card_id in targets:
        raise ValueError("Una scheda non può collegarsi a se stessa.")
    if targets:
        rows = connection.execute(
            "SELECT id FROM memory_cards WHERE id = ANY(%s) AND scope = ANY(%s)",
            (list(targets), visible_scopes(scope)),
        ).fetchall()
        if {row["id"] for row in rows} != targets:
            raise ValueError("I collegamenti devono puntare a schede esistenti nello stesso ambito o in un suo antenato.")
    if document.source_runs:
        rows = connection.execute(
            "SELECT id FROM runtime_runs WHERE id = ANY(%s)", (document.source_runs,),
        ).fetchall()
        if {row["id"] for row in rows} != set(document.source_runs):
            raise ValueError("Una delle esecuzioni indicate come fonte non esiste.")


def _save_card(connection, document: CardCreate | CardEdit, card_id: UUID | None = None) -> dict:
    if isinstance(document, CardCreate):
        card_id, scope, version = uuid4(), document.scope, 1
        created = connection.execute(
            """INSERT INTO memory_cards (id, scope, slug, current_version)
               VALUES (%s, %s, %s, 1) ON CONFLICT (scope, slug) DO NOTHING RETURNING id""",
            (card_id, scope, document.slug),
        ).fetchone()
        if not created:
            raise MemoryConflict("Esiste già una scheda con questa chiave nell'ambito.")
    else:
        card = connection.execute(
            "SELECT scope, current_version FROM memory_cards WHERE id = %s FOR UPDATE", (card_id,),
        ).fetchone()
        if not card:
            raise KeyError(card_id)
        if card["current_version"] != document.expected_version:
            raise MemoryConflict("La scheda è cambiata. Riaprila prima di salvare.")
        scope, version = card["scope"], document.expected_version + 1

    _validate_references(connection, card_id, scope, document)
    connection.execute(
        "INSERT INTO memory_card_versions (card_id, version, document) VALUES (%s, %s, %s)",
        (card_id, version, Jsonb(document.model_dump(
            mode="json", exclude={"scope", "slug", "expected_version"},
        ))),
    )
    if version > 1:
        connection.execute(
            "UPDATE memory_cards SET current_version = %s WHERE id = %s", (version, card_id),
        )
    return connection.execute(_CARD_SELECT + " WHERE c.id = %s", (card_id,)).fetchone()


def save_card(document: CardCreate | CardEdit, card_id: UUID | None = None) -> dict:
    """Store one immutable revision. Identity and scope are fixed after creation."""
    with db_connection() as connection:
        return _save_card(connection, document, card_id)


class StarterDrafts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["serveria-memory-drafts-v1"]
    cards: list[CardCreate] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def draft_only(self):
        keys = {(item.scope, item.slug) for item in self.cards}
        if len(keys) != len(self.cards):
            raise ValueError("Il file contiene due schede con lo stesso ambito e chiave.")
        if any(item.state != "draft" for item in self.cards):
            raise ValueError("L'importazione accetta solo bozze. Approva le schede nella biblioteca.")
        return self


def import_drafts(drafts: StarterDrafts) -> list[dict]:
    """Create the entire bundle in a single transaction, preserving existing cards."""
    with db_connection() as connection:
        return [
            _save_card(connection, draft)
            for draft in sorted(drafts.cards, key=lambda item: (item.scope, item.slug))
        ]


def get_card(card_id: UUID, version: int | None = None) -> dict:
    with db_connection() as connection:
        if version is None:
            row = connection.execute(_CARD_SELECT + " WHERE c.id = %s", (card_id,)).fetchone()
        else:
            row = connection.execute(
                """SELECT c.id, c.scope, c.slug, v.version, v.document, v.created_at
                   FROM memory_cards c JOIN memory_card_versions v ON v.card_id = c.id
                   WHERE c.id = %s AND v.version = %s""", (card_id, version),
            ).fetchone()
    if not row:
        raise KeyError(card_id)
    return row


def list_cards(scope: str, query: str = "", state: str = "", after: str = "", limit: int = 50):
    """Find cards in the selected scope. Use the slug as the pagination cursor."""
    with db_connection() as connection:
        return connection.execute(
            """SELECT c.id, c.scope, c.slug, v.version, v.created_at,
                      v.document->>'title' AS title, v.document->>'description' AS description,
                      v.document->>'kind' AS kind, v.document->>'state' AS state
               FROM memory_cards c JOIN memory_card_versions v
                   ON v.card_id = c.id AND v.version = c.current_version
               WHERE c.scope = %s AND c.slug > %s AND (%s = '' OR v.document->>'state' = %s)
                 AND (%s = '' OR strpos(lower(concat_ws(' ', c.slug, v.document->>'title',
                     v.document->>'description', v.document->>'content')), lower(%s)) > 0)
               ORDER BY c.slug LIMIT %s""",
            (scope, after, state, state, query, query, limit),
        ).fetchall()


def export_cards(scope: str, *, after: str = "", limit: int = 20):
    """Explicit export of current approved cards, with provenance and stable versions."""
    with db_connection() as connection:
        return connection.execute(
            _CARD_SELECT + f""" WHERE c.scope = %s AND c.slug > %s
                AND v.document->>'state' = 'approved' AND {_VALID_NOW}
                ORDER BY c.slug LIMIT %s""",
            (scope, after, limit),
        ).fetchall()


def list_scopes(after: str = "", limit: int = 50) -> list[str]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT scope FROM memory_cards WHERE scope > %s ORDER BY scope LIMIT %s",
            (after, limit),
        ).fetchall()
    return [row["scope"] for row in rows]
