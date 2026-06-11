"""Mock provider adapter — loads canned fixture data from enrichment_responses.json."""

import json
import os


def load_mocks():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'mocks', 'enrichment_responses.json')
    with open(path) as f:
        return json.load(f)


def lookup(mocks, company_name):
    """Return (registry, listing, enrichment) for company_name; each is None if absent."""
    data = mocks.get(company_name)
    if not data:
        return None, None, None
    return data.get('registry'), data.get('listing'), data.get('enrichment')
