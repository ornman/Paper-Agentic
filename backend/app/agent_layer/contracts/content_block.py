from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Discriminator, Tag


class BlockCitation(BaseModel):
    sourceId: str


class BlockParagraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str
    citations: list[BlockCitation] | None = None


class BlockHeading(BaseModel):
    type: Literal["heading"] = "heading"
    level: Literal[1, 2, 3, 4]
    text: str


class BlockList(BaseModel):
    type: Literal["list"] = "list"
    ordered: bool
    items: list[str]


class BlockCitationText(BaseModel):
    type: Literal["citation_block"] = "citation_block"
    text: str
    sourceIds: list[str]


class BlockTable(BaseModel):
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]


class BlockCode(BaseModel):
    type: Literal["code"] = "code"
    language: str
    code: str


class BlockDivider(BaseModel):
    type: Literal["divider"] = "divider"


ContentBlock = Annotated[
    Annotated[BlockParagraph, Tag("paragraph")]
    | Annotated[BlockHeading, Tag("heading")]
    | Annotated[BlockList, Tag("list")]
    | Annotated[BlockCitationText, Tag("citation_block")]
    | Annotated[BlockTable, Tag("table")]
    | Annotated[BlockCode, Tag("code")]
    | Annotated[BlockDivider, Tag("divider")],
    Discriminator("type"),
]
