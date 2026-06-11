#!/usr/bin/env python3
"""
Contact finder — Stage B slice.

Reads data/companies.csv, queries mock providers, writes output/contacts.csv.

Usage:
    python solution/main.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from providers import load_mocks, lookup
from resolver import resolve_contact

ROOT = os.path.join(os.path.dirname(__file__), '..')
INPUT_CSV = os.path.join(ROOT, 'data', 'companies.csv')
OUTPUT_CSV = os.path.join(ROOT, 'output', 'contacts.csv')

FIELDNAMES = [
    'company_name',
    'contact_name',
    'contact_role',
    'contact_email_or_phone',
    'confidence_score',
    'source',
    'needs_human_review',
]


def run():
    mocks = load_mocks()
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    rows = []
    with open(INPUT_CSV, newline='') as f:
        for row in csv.DictReader(f):
            company = row['company_name']
            registry, listing, enrichment = lookup(mocks, company)
            result = resolve_contact(registry, listing, enrichment)
            rows.append({'company_name': company, **result})

    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    auto = sum(1 for r in rows if not r['needs_human_review'])
    review = len(rows) - auto
    print(f"Processed {len(rows)} companies → {auto} automated, {review} need human review")
    print(f"Output: {os.path.abspath(OUTPUT_CSV)}")


if __name__ == '__main__':
    run()
