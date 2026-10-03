"""Guard the protocol registry until verified identity and RBAC are integrated."""

from cte.api import app


def test_protocol_registry_mutation_routes_remain_unexposed():
    """Shared API keys are not proof of distinct author/reviewer/approver identities."""
    exposed = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    mutation_routes = {
        ("POST", "/protocols/v1/register"),
        ("POST", "/protocols/v1/review"),
        ("POST", "/protocols/v1/transition"),
        ("POST", "/protocols/v1/activate"),
        ("POST", "/protocols/v1/suspend"),
        ("POST", "/protocols/v1/retire"),
    }
    assert exposed.isdisjoint(mutation_routes)


def test_only_review_candidate_selection_routes_are_currently_exposed():
    exposed = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/protocols/v1/")
    }
    assert exposed == {
        ("POST", "/protocols/v1/select-candidates"),
        ("POST", "/protocols/v1/select-registered-candidates"),
    }
