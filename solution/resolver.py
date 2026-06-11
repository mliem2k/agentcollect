"""Contact resolution: name normalisation, cross-source agreement, confidence scoring."""

import re

CONFIDENCE_THRESHOLD = 70

# Lower number = higher priority for outreach. Source: CLARIFICATIONS.md.
_ROLE_PRIORITY = {
    'ap manager': 0,
    'accounts payable': 0,
    'accounts payable manager': 0,
    'controller': 1,
    'cfo': 1,
    'chief financial officer': 1,
    'finance': 1,
    'owner': 2,
    'founder': 2,
    'co-founder': 2,
    'partner': 2,
    'president': 2,
    'manager': 3,
    'office manager': 3,
    'director': 4,
    # Registered Agent is a legal designation, not a business decision-maker.
    'registered agent': 9,
}

_NICKNAME_MAP = {
    'bob': 'robert', 'rob': 'robert', 'robbie': 'robert',
    'bill': 'william', 'will': 'william', 'willie': 'william',
    'jim': 'james', 'jimmy': 'james',
    'kate': 'katherine', 'kathy': 'katherine', 'katie': 'katherine',
    'mike': 'michael', 'mick': 'michael',
    'dan': 'daniel', 'danny': 'daniel',
    'dave': 'david', 'davy': 'david',
    'steve': 'stephen',
    'jeff': 'jeffrey',
    'liz': 'elizabeth', 'beth': 'elizabeth', 'bess': 'elizabeth',
    'joe': 'joseph',
    'jon': 'jonathan',
    'chris': 'christopher',
    'pat': 'patricia',
    'tony': 'anthony',
    'ben': 'benjamin',
    'matt': 'matthew',
    'rick': 'richard', 'dick': 'richard',
    'tom': 'thomas',
    'ted': 'edward', 'ned': 'edward', 'ed': 'edward',
    'sue': 'susan', 'susie': 'susan',
    'cindy': 'cynthia',
    'sam': 'samuel',
    'andy': 'andrew',
    'alex': 'alexander',
    'nate': 'nathaniel',
}

_HONORIFICS = {'dr', 'mr', 'mrs', 'ms', 'miss', 'prof', 'rev', 'sr', 'jr'}

_GENERIC_EMAIL_PREFIXES = {
    'info', 'sales', 'office', 'contact', 'admin', 'support', 'hello',
    'team', 'billing', 'accounts', 'ap', 'finance', 'hr', 'mail', 'post',
    'general', 'enquiries', 'inquiries', 'help', 'service', 'services',
    'webmaster', 'noreply', 'no-reply',
}


def _normalize_name(name):
    """Lowercase, strip honorifics, strip parentheticals, apply nickname map."""
    if not name:
        return None
    parts = re.sub(r'\([^)]*\)', '', name).split()
    parts = [p.rstrip('.').lower() for p in parts if p.rstrip('.').lower() not in _HONORIFICS]
    parts = [_NICKNAME_MAP.get(p, p) for p in parts]
    result = ' '.join(parts).strip()
    return result or None


def _names_match(a, b):
    """True when two raw name strings refer to the same person."""
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    parts_a, parts_b = na.split(), nb.split()
    if len(parts_a) < 2 or len(parts_b) < 2:
        return False
    if parts_a[-1] != parts_b[-1]:
        return False
    # Accept first-initial match: "S. Murphy" matches "Sean Murphy"
    fa, fb = parts_a[0], parts_b[0]
    if fa == fb:
        return True
    if len(fa) == 1 and fb.startswith(fa):
        return True
    if len(fb) == 1 and fa.startswith(fb):
        return True
    return False


def _role_priority(role):
    return _ROLE_PRIORITY.get((role or '').lower().strip(), 5)


def _is_valid_outreach_role(role):
    """False for roles that identify a legal agent rather than a business contact."""
    return _role_priority(role) < 9


def _is_generic_email(email):
    prefix = re.split(r'[@+\d]', email)[0].lower()
    return prefix in _GENERIC_EMAIL_PREFIXES


def _clean_display_name(name):
    """Strip parenthetical suffixes for clean output while keeping the core name."""
    return re.sub(r'\s*\([^)]+\)', '', name).strip() if name else name


def resolve_contact(registry, listing, enrichment):
    """
    Aggregate signals from up to three independent providers and return a
    single best-candidate contact with confidence score and provenance.

    Output keys: contact_name, contact_role, contact_email_or_phone,
                 confidence_score, source, needs_human_review
    """
    reg_name = (registry or {}).get('name')
    reg_role = (registry or {}).get('role')
    reg_url = (registry or {}).get('source_url')

    list_name = (listing or {}).get('name')
    list_phone = (listing or {}).get('phone')
    list_url = (listing or {}).get('source_url')

    enr_email = (enrichment or {}).get('email')
    enr_phone = (enrichment or {}).get('phone')
    enr_conf = (enrichment or {}).get('provider_confidence', 0)
    enr_url = (enrichment or {}).get('source_url')

    # --- Name agreement / conflict ---
    names_conflict = False
    names_agree = False
    if reg_name and list_name:
        if _names_match(reg_name, list_name):
            names_agree = True
        else:
            names_conflict = True

    # --- Select best name (registry wins on conflict) ---
    best_name = reg_name or list_name

    # --- Select best role by outreach priority ---
    role_candidates = []
    if reg_role:
        role_candidates.append((_role_priority(reg_role), reg_role))
    if list_name and '(' in list_name:
        m = re.search(r'\(([^)]+)\)', list_name)
        if m:
            inferred = m.group(1)
            role_candidates.append((_role_priority(inferred), inferred))
    best_role = sorted(role_candidates)[0][1] if role_candidates else None

    # --- Select contact method (email preferred; listing phone excluded on conflict) ---
    contact = ''
    contact_source_urls = []
    if enr_email:
        contact = enr_email
        contact_source_urls.append(enr_url)
    elif enr_phone:
        contact = enr_phone
        contact_source_urls.append(enr_url)
    elif list_phone and not names_conflict:
        contact = list_phone
        contact_source_urls.append(list_url)

    # --- Build provenance (source URLs for every contributed signal) ---
    name_source_urls = []
    if best_name == reg_name and reg_url:
        name_source_urls.append(reg_url)
        if names_agree and list_url:
            name_source_urls.append(list_url)
    elif best_name == list_name and list_url:
        name_source_urls.append(list_url)

    all_urls = dict.fromkeys(name_source_urls + contact_source_urls)  # ordered dedup
    source_str = ', '.join(u for u in all_urls if u)

    # --- Confidence score ---
    score = _compute_confidence(
        reg_name=reg_name, reg_role=reg_role,
        list_name=list_name, list_phone=list_phone,
        enr_email=enr_email, enr_phone=enr_phone, enr_conf=enr_conf,
        names_agree=names_agree, names_conflict=names_conflict,
    )

    needs_review = score < CONFIDENCE_THRESHOLD

    return {
        'contact_name': _clean_display_name(best_name) or '',
        'contact_role': best_role or '',
        'contact_email_or_phone': '' if needs_review else contact,
        'confidence_score': score,
        'source': source_str,
        'needs_human_review': needs_review,
    }


def _compute_confidence(
    reg_name, reg_role, list_name, list_phone,
    enr_email, enr_phone, enr_conf,
    names_agree, names_conflict,
):
    score = 0

    # Registry identity (most authoritative source)
    if reg_name:
        score += 35
        if reg_role and _is_valid_outreach_role(reg_role):
            score += 10

    # Listing name signal
    if list_name:
        if names_agree:
            score += 20   # independent corroboration
        elif not names_conflict and not reg_name:
            score += 10   # listing is the only name source

    if names_conflict:
        score -= 20

    # Enrichment contact channel
    if enr_email:
        score += 3 if _is_generic_email(enr_email) else 15
        if enr_conf >= 80:
            score += 15
        elif enr_conf >= 70:
            score += 12
        elif enr_conf >= 60:
            score += 8
        elif enr_conf >= 40:
            score += 4

    if enr_phone:
        score += 3

    # Listing phone (not attributed on conflict)
    if list_phone and not names_conflict:
        score += 2

    # Cross-source phone confirmation
    if list_phone and enr_phone and list_phone == enr_phone:
        score += 5

    return min(100, max(0, score))
