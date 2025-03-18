from fastapi import FastAPI
from fastapi.routing import APIRoute
from typing import List, cast
from cuid2 import Cuid


def use_route_names_as_operation_ids(application: FastAPI) -> None:
    """
    Simplify operation IDs so that generated API clients have simpler function
    names.

    Should be called only after all routes have been added.
    """
    for route in cast(List[APIRoute], application.routes):
        if isinstance(route, APIRoute):
            route: APIRoute = route
            route.operation_id = route.name


def make_cuid(prefix: str) -> str:
    """
    Generates a CUID (Collision-resistant internal identifier) with the given prefix.

    Args:
        prefix (str): The prefix to be added to the generated CUID.

    Returns:
        str: The generated CUID with the prefix appended.

    """
    id = Cuid(length=23).generate()
    return f"{prefix}{id}"
