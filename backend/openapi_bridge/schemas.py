"""
Pydantic schemas for the OpenAPI Bridge module.

Covers:
  - ParameterInfo: individual parameter metadata (path/query/header)
  - EndpointInfo: one operation from an OpenAPI path
  - ParseRequest/ParseResponse: admin parse endpoint I/O
  - RegisterRequest/RegisterResponse: admin register endpoint I/O
"""
from typing import Any

from pydantic import BaseModel


class ParameterInfo(BaseModel):
    """Metadata for a single OpenAPI parameter."""

    name: str
    location: str  # "path" | "query" | "header"
    required: bool
    schema_type: str  # "string" | "integer" | "boolean" | "number" | "array" | "object"
    description: str | None = None


class EndpointInfo(BaseModel):
    """One operation from an OpenAPI spec path item."""

    operation_id: str | None
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    summary: str | None
    description: str | None
    tags: list[str]
    parameters: list[ParameterInfo]
    request_body_schema: dict[str, Any] | None = None
    deprecated: bool = False


class ParseRequest(BaseModel):
    """Request body for the parse endpoint."""

    url: str  # URL to fetch the OpenAPI spec from


class ParseResponse(BaseModel):
    """Response from the parse endpoint."""

    base_url: str
    title: str | None
    version: str | None
    endpoints: list[EndpointInfo]
    tag_groups: dict[str, list[int]]  # tag -> list of endpoint indices for UI grouping


class RegisterRequest(BaseModel):
    """Request body for the register endpoint."""

    server_name: str
    base_url: str
    spec_url: str
    selected_endpoints: list[EndpointInfo]
    auth_type: str  # "bearer" | "api_key" | "basic" | "none"
    auth_value: str | None = None  # API key, token, or "user:pass" for basic
    auth_header: str | None = None  # custom header name for api_key type


class RegisterResponse(BaseModel):
    """Response from the register endpoint."""

    server_id: str
    tools_created: int
