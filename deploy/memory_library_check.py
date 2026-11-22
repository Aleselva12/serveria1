"""Isolated fixtures for the live Memory Library check."""
from core.domain.memory import MemoryConflict
from core.domain.memory_library import CardCreate, CardEdit, export_cards, get_card, list_cards, save_card
from core.infra.database import db_connection


def _document(**updates):
    return {
        "title": "Nota sintetica di collaudo",
        "description": "Scheda temporanea creata dal verificatore",
        "content": "prima versione",
        "kind": "brief",
        **updates,
    }


def write(scope):
    source = save_card(CardCreate(scope=scope, slug="decision", **_document()))
    document = _document(
        state="approved", content="versione corretta",
        relations=[{"target_id": source["id"], "kind": "depends_on"}],
    )
    child = save_card(CardCreate(scope=scope + "/project", slug="design", **_document()))
    edit = CardEdit(expected_version=1, **document)
    save_card(edit, child["id"])
    try:
        save_card(edit, child["id"])
    except MemoryConflict:
        return
    raise ValueError("Revisione obsoleta accettata")


def read(scope):
    project = scope + "/project"
    parent = list_cards(scope, query="temporanea")
    children = list_cards(project, query="sintetica")
    if len(parent) != 1 or len(children) != 1 or list_cards(scope + "/other"):
        raise ValueError("Ricerca o isolamento degli ambiti non riusciti")
    card = get_card(children[0]["id"])
    previous = get_card(card["id"], 1)
    if (
        card["version"] != 2 or previous["document"]["state"] != "draft"
        or card["document"]["content"] != "versione corretta"
        or card["document"]["relations"][0]["target_id"] != str(parent[0]["id"])
        or [item["id"] for item in export_cards(project)] != [card["id"]]
        or export_cards(scope)
    ):
        raise ValueError("Revisione, collegamento o esportazione non riusciti")


def cleanup(scope):
    with db_connection(ensure_schema=False) as connection:
        connection.execute(
            "DELETE FROM memory_cards WHERE scope = ANY(%s) AND slug = ANY(%s)",
            ([scope, scope + "/project"], ["decision", "design"]),
        )
