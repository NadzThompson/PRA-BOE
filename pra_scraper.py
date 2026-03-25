#!/usr/bin/env python3
"""
PRA Rulebook Scraper
====================
Scrapes the PRA Rulebook (Rules, Guidance, Glossary) from prarulebook.co.uk
and outputs clean content in PDF, JSON, Markdown, and HTML formats.
"""

import os
import sys
import json
import time
import re
import html as html_module
import traceback
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup, Comment
import html2text
from fpdf import FPDF

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = "https://www.prarulebook.co.uk"
DATE_PARAM = "03-03-2026"
OUTPUT_DIR = Path(r"C:\Users\nadin\OneDrive\Documents\NOVA\PRA")
REQUEST_DELAY = 0.6  # seconds between requests to be polite
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
})

# Noise patterns to remove from scraped content
NOISE_PATTERNS = [
    r'(?i)convert\s+to\s+pdf',
    r'(?i)email\s+this\s+page',
    r'(?i)print\s+this\s+page',
    r'(?i)share\s+via\s+email',
    r'(?i)send\s+to\s+kindle',
    r'(?i)cookie\s+(?:policy|settings|preferences)',
    r'(?i)subscribe\s+to\s+updates',
    r'(?i)sign\s+up\s+for',
    r'(?i)newsletter',
]

# ─── URL Catalogues ──────────────────────────────────────────────────────────

RULES_SLUGS = [
    # CRR Firms (Banking & Investment)
    "algorithmic-trading",
    "allocation-of-responsibilities",
    "audit-committee",
    "benchmarking-of-internal-approaches",
    "capital-buffers",
    "compliance-and-internal-audit",
    "counterparty-credit-risk-crr",
    "counterparty-credit-risk",
    "credit-risk",
    "credit-risk---standardised-approach-crr",
    "credit-valuation-adjustment-risk-crr",
    "definition-of-capital",
    "designation",
    "disclosure-crr",
    "general-organisational-requirements",
    "group-risk-systems",
    "groups",
    "housing",
    "internal-capital-adequacy-assessment",
    "internal-liquidity-adequacy-assessment",
    "large-exposures",
    "large-exposures-crr",
    "leverage-ratio-crr",
    "leverage-ratio-capital-requirements-and-buffers",
    "liquidity-crr",
    "liquidity-coverage-ratio-crr",
    "liquidity-coverage-requirement---uk-designated-investment-firms",
    "market-risk",
    "non-performing-exposures-securitisation-crr",
    "operational-continuity",
    "operational-resilience",
    "operational-risk-crr",
    "outsourcing",
    "own-funds-crr",
    "permissions",
    "public-disclosure",
    "record-keeping",
    "related-party-transaction-risk",
    "remuneration",
    "reporting-crr",
    "reporting-leverage-ratio",
    "reporting-pillar-2",
    "resolution-assessment",
    "risk-control",
    "sddt-regime--general-application",
    "skills-knowledge-and-expertise",
    "standardised-approach-and-internal-ratings-based-approach-to-credit-risk-crr",
    "step-in-risk",
    "supervised-run-off",
    "trading-book-crr",
    "waivers-transitional-provisions",
    # Non-CRR Firms
    "certification",
    "conduct-rules",
    "credit-unions",
    "fitness-and-propriety",
    "internal-governance-of-third-country-branches",
    "regulatory-reporting",
    "senior-management-functions",
    "senior-managers-regime---applications-and-notifications",
    "third-country-firms",
    # SII Firms (Insurance)
    "actuaries",
    "composites",
    "conditions-governing-business",
    "group-supervision",
    "insurance---allocation-of-responsibilities",
    "insurance---certification",
    "insurance---conduct-standards",
    "insurance---fitness-and-propriety",
    "insurance---operational-resilience",
    "insurance---senior-management-functions",
    "insurance---senior-managers-regime---applications-and-notifications",
    "insurance---senior-managers-regime---transitional-provisions",
    "insurance-general-application",
    "insurance-special-purpose-vehicles",
    "insurance-supervised-run-off",
    "insurers-in-financial-difficulties-notification-of-affected-persons",
    "investments",
    "key-function-holder---notifications",
    "lloyds",
    "lloyds-actuaries-auditors-and-fscs",
    "matching-adjustment",
    "minimum-capital-requirement",
    "own-funds",
    "reporting",
    "run-off-operations-solvency-ii",
    "solvency-capital-requirement---general-provisions",
    "solvency-capital-requirement---internal-models",
    "solvency-capital-requirement---standard-formula",
    "solvency-capital-requirement---undertaking-specific-parameters",
    "surplus-funds",
    "technical-provisions",
    "technical-provisions-further-requirements",
    "third-country-branches",
    "transitional-measure-on-technical-provisions",
    "transitional-measures",
    "undertakings-in-difficulty",
    "valuation",
    "whistleblowing",
    "with-profits",
    # Non-SII Firms
    "friendly-society---asset-valuation",
    "friendly-society---overall-resources-and-guarantee-fund",
    "friendly-society---reporting",
    "friendly-society-financial-prudence",
    "friendly-society-liability-valuation",
    "friendly-society-required-margin",
    "insurance-company---capital-resources",
    "insurance-company---internal-contagion-risk",
    "insurance-company---reporting",
    "insurance-company---technical-provisions",
    "insurance-company-capital-resources-requirements",
    "insurance-company-capital-resources-table",
    "insurance-company-exposure-limits",
    "insurance-company-mathematical-reserves",
    "insurance-company-overall-resources-and-valuation",
    "insurance-company-risk-management",
    "large-non-solvency-ii-firms-allocation-of-responsibilities",
    "large-non-solvency-ii-firms-certification",
    "large-non-solvency-ii-firms-conduct-standards",
    "large-non-solvency-ii-firms-fitness-and-propriety",
    "large-non-solvency-ii-firms-key-function-holder-notifications",
    "large-non-solvency-ii-firms-senior-management-functions",
    "large-non-solvency-ii-firms-senior-managers-regime-applications-and-notifications",
    "large-non-solvency-ii-firms-senior-managers-regime-transitional-provisions",
    "non-solvency-ii-firms---conduct-standards",
    "non-solvency-ii-firms---fitness-and-propriety",
    "non-solvency-ii-firms---run-off-firms",
    "non-solvency-ii-firms---senior-management-functions",
    "non-solvency-ii-firms-actuarial-requirements",
    "non-solvency-ii-firms-certification",
    "non-solvency-ii-firms-governance",
    "non-solvency-ii-firms-senior-managers-regime-applications-and-notifications",
    "non-solvency-ii-firms-senior-managers-regime-transitional-provisions",
    "non-solvency-ii-firms-with-profits",
    "non-solvency-ii-firms---allocation-of-responsibilities",
    "nonsolvency-ii-firms-transitional-measures",
    "run-off-operations-non_directive-insurers",
    # Cross-Applicant Rules
    "auditors",
    "change-in-control",
    "close-links",
    "depositor-protection",
    "dormant-account-scheme",
    "external-audit",
    "fees",
    "financial-conglomerates",
    "fundamental-rules",
    "general-provisions",
    "group-financial-support",
    "information-gathering",
    "interpretation",
    "management-expenses-in-respect-of-relevant-schemes",
    "notifications",
    "passporting-deleted",
    "permissions-and-waivers",
    "policyholder-protection",
    "recovery-and-resolution",
    "remuneration-reporting-requirements",
    "securitisation",
    "use-of-skilled-persons",
    # Non-Authorised Persons
    "contractual-recognition-of-bail-in",
    "critical-third-parties",
    "fscs-management-expenses-levy-limit-and-base-costs",
    "recovery-plans",
    "resolution-pack",
    "ring-fenced-bodies",
    "stay-in-resolution",
    "senior-managers-regime---transitional-provisions",
]

# Remove duplicates while preserving order
RULES_SLUGS = list(dict.fromkeys(RULES_SLUGS))

GUIDANCE_SLUGS = [
    # Supervisory Statements
    ("supervisory-statements", "lss07-13----the-relationship-between-the-external-auditor-and-the-supervisor-a-code-of-practice"),
    ("supervisory-statements", "ss01-14---mutuality-and-with-profits-funds"),
    ("supervisory-statements", "ss01-15---insurance-general-application"),
    ("supervisory-statements", "ss01-16---written-reports-by-external-auditors-to-the-pra"),
    ("supervisory-statements", "ss01-17-supervising-international-banks"),
    ("supervisory-statements", "ss01-19---non-binding-pra-materials"),
    ("supervisory-statements", "ss01-20-solvency-ii-prudent-person-principle"),
    ("supervisory-statements", "ss01-21---operational-resilience-impact-tolerances-for-important-business-services"),
    ("supervisory-statements", "ss01-22-trading-activity-wind-down"),
    ("supervisory-statements", "ss01-23--model-risk-management-principles-for-banks"),
    ("supervisory-statements", "ss01-24--internal-model-requirements-for-insurers"),
    ("supervisory-statements", "ss01-25-step-in-risk"),
    ("supervisory-statements", "ss10-13---standardised-approach"),
    ("supervisory-statements", "ss10-16---solvency-ii-remuneration"),
    ("supervisory-statements", "ss10-18---securitisation-general-requirements-and-capital-framework"),
    ("supervisory-statements", "ss10-24---acquisitions-and-increases-in-control"),
    ("supervisory-statements", "ss11-13---internal-ratings-based-approaches"),
    ("supervisory-statements", "ss11-15---solvency-ii-regulatory-reporting-and-exemptions"),
    ("supervisory-statements", "ss11-16---solvency-ii-external-audit-and-governance"),
    ("supervisory-statements", "ss12-13---counterparty-credit-risk"),
    ("supervisory-statements", "ss12-15---solvency-ii-lloyds"),
    ("supervisory-statements", "ss12-16---solvency-ii-changes-to-internal-models-used-by-uk-insurance-firms"),
    ("supervisory-statements", "ss13-13---market-risk"),
    ("supervisory-statements", "ss13-15---solvency-ii-surplus-funds"),
    ("supervisory-statements", "ss13-16---underwriting-standards-for-buy-to-let-mortgage-contracts"),
    ("supervisory-statements", "ss14-13---operational-risk"),
    ("supervisory-statements", "ss14-15---solvency-ii-with-profits"),
    ("supervisory-statements", "ss14-16---reporting-instructions-for-non-solvency-ii-firms"),
    ("supervisory-statements", "ss15-13---groups"),
    ("supervisory-statements", "ss15-15---solvency-ii-approvals"),
    ("supervisory-statements", "ss15-16---model-drift-and-standard-formula-scr-reporting-for-insurers"),
    ("supervisory-statements", "ss16-13---large-exposures"),
    ("supervisory-statements", "ss16-15---solvency-ii-conditions-governing-business"),
    ("supervisory-statements", "ss16-16---minimum-requirement-for-own-funds-and-eligible-liabilities-mrel"),
    ("supervisory-statements", "ss17-13---credit-risk-mitigation"),
    ("supervisory-statements", "ss17-15---solvency-ii-transitional-measures"),
    ("supervisory-statements", "ss17-16---internal-models---assessment-model-change-and-the-role-of-non-executive-directors"),
    ("supervisory-statements", "ss18-15---depositor-protection"),
    ("supervisory-statements", "ss18-16---longevity-risk-transfers"),
    ("supervisory-statements", "ss19-13---resolution-planning"),
    ("supervisory-statements", "ss19-15---building-societies-act-functions"),
    ("supervisory-statements", "ss19-16---solvency-ii-orsa"),
    ("supervisory-statements", "ss02-14---deferred-tax-and-solvency-ii"),
    ("supervisory-statements", "ss02-15---solvency-ii-own-funds"),
    ("supervisory-statements", "ss02-17---remuneration"),
    ("supervisory-statements", "ss02-18---international-insurers-the-pras-approach-to-branch-authorisation-and-supervision"),
    ("supervisory-statements", "ss02-19---pra-approach-to-interpreting-reporting-and-disclosure-requirements-and-regulatory-transactions-forms-after-the-uks-withdrawal-from-the-eu"),
    ("supervisory-statements", "ss02-21---outsourcing-and-third-party-risk-management"),
    ("supervisory-statements", "ss02-23---pra-approach-to-supervising-and-regulating-credit-unions"),
    ("supervisory-statements", "ss02-24--solvent-exit-planning-for-non-systemic-banks-and-building-societies"),
    ("supervisory-statements", "ss02-25-insurance-risk-transfer-to-special-purpose-vehicles"),
    ("supervisory-statements", "ss20-13---third-country-equivalence"),
    ("supervisory-statements", "ss20-15---supervising-building-societies-treasury-and-lending-activities"),
    ("supervisory-statements", "ss20-16---solvency-ii-reinsurance-counterparty-credit-risk"),
    ("supervisory-statements", "ss21-15---internal-governance"),
    ("supervisory-statements", "ss22-15---solvency-ii-eiopa-set-1-guidelines"),
    ("supervisory-statements", "ss23-15---solvency-ii-supervisory-approval-for-the-volatility-adjustment"),
    ("supervisory-statements", "ss24-15---the-pras-approach-to-supervising-liquidity-and-funding-risks"),
    ("supervisory-statements", "ss25-15---solvency-ii-regulatory-reporting-internal-model-outputs"),
    ("supervisory-statements", "ss26-15---solvency-ii-orsa-and-the-ultimate-time-horizon"),
    ("supervisory-statements", "ss28-15---strengthening-individual-accountability-in-banking"),
    ("supervisory-statements", "ss03-14---solvency-ii-insurance---loss-absorbing-capacity-of-deferred-taxes-under-solvency-ii"),
    ("supervisory-statements", "ss03-15---solvency-ii-quality-of-capital-instruments"),
    ("supervisory-statements", "ss03-16---pra-approach-to-fees"),
    ("supervisory-statements", "ss03-17---solvency-ii-illiquid-unrated-assets"),
    ("supervisory-statements", "ss03-18---model-risk-management-principles-for-stress-testing"),
    ("supervisory-statements", "ss03-19---enhancing-banks-and-insurers-approaches-to-managing-the-financial-risks-from-climate-change"),
    ("supervisory-statements", "ss03-21---the-pras-approach-to-new-and-growing-banks"),
    ("supervisory-statements", "ss03-25-connected-clients-identification-for-large-exposures"),
    ("supervisory-statements", "ss30-15---solvency-ii-treatment-of-sovereign-debt"),
    ("supervisory-statements", "ss31-15---the-internal-capital-adequacy-assessment-process-icaap-and-the-supervisory-review-and-evaluation-process-srep"),
    ("supervisory-statements", "ss32-15---pillar-2-reporting-instructions"),
    ("supervisory-statements", "ss33-15---aggregation-of-holdings-for-the-purpose-of-controllers"),
    ("supervisory-statements", "ss34-15---guidelines-for-completing-regulatory-reports"),
    ("supervisory-statements", "ss35-15---strengthening-individual-accountability-in-insurance"),
    ("supervisory-statements", "ss36-15---solvency-ii-life-insurance-product-codes"),
    ("supervisory-statements", "ss37-15---solvency-ii-internal-model-reporting-codes"),
    ("supervisory-statements", "ss38-15---solvency-ii-consistency-of-the-approach-to-reporting-with-uk-gaap-or-ifrs"),
    ("supervisory-statements", "ss39-15---whistleblowing-in-deposit-takers-pra-designated-investment-firms-and-insurers"),
    ("supervisory-statements", "ss04-14---capital-extractions-by-run-off-firms-within-the-scope-of-solvency-ii"),
    ("supervisory-statements", "ss04-15---solvency-capital-requirement-and-minimum-capital-requirement"),
    ("supervisory-statements", "ss04-16---the-pras-expectations-on-the-internal-governance-of-third-country-branches"),
    ("supervisory-statements", "ss04-17---cyber-insurance-underwriting-risk"),
    ("supervisory-statements", "ss04-18---financial-management-and-planning-by-insurers"),
    ("supervisory-statements", "ss04-19---pra-approach-to-interpreting-reporting-and-disclosure-requirements-and-regulatory-transactions-forms-after-the-uks-withdrawal-from-the-eu"),
    ("supervisory-statements", "ss04-21---operational-continuity-in-resolution"),
    ("supervisory-statements", "ss40-15---solvency-ii-reporting-and-public-disclosure---expectations"),
    ("supervisory-statements", "ss41-15---solvency-ii-eiopa-set-2-guidelines"),
    ("supervisory-statements", "ss42-15---contractual-stays-in-financial-contracts-governed-by-third-country-law"),
    ("supervisory-statements", "ss43-15---non-solvency-ii-firms-capital-assessments"),
    ("supervisory-statements", "ss44-15---third-country-insurance-and-reinsurance-branches"),
    ("supervisory-statements", "ss45-15---the-uk-leverage-ratio-framework"),
    ("supervisory-statements", "ss05-14---solvency-ii-technical-provisions"),
    ("supervisory-statements", "ss05-15---solvency-ii-pension-scheme-risk"),
    ("supervisory-statements", "ss05-16---corporate-governance-board-responsibilities"),
    ("supervisory-statements", "ss05-17---dealing-with-a-market-turning-event-in-the-general-insurance-sector"),
    ("supervisory-statements", "ss05-18---algorithmic-trading"),
    ("supervisory-statements", "ss05-19---liquidity-and-funding-risk-management-by-insurers"),
    ("supervisory-statements", "ss05-21---international-banks-the-pras-approach-to-branch-and-subsidiary-supervision"),
    ("supervisory-statements", "ss05-24---funded-reinsurance"),
    ("supervisory-statements", "ss05-25-the-pras-approach-to-the-management-of-climate-related-financial-risks"),
    ("supervisory-statements", "ss06-14---capital-buffers"),
    ("supervisory-statements", "ss06-15---solvency-ii-internal-models---treatment-of-participations"),
    ("supervisory-statements", "ss06-16---maintenance-of-the-transitional-measure-on-technical-provisions"),
    ("supervisory-statements", "ss06-18---solvency-ii-national-specific-templates"),
    ("supervisory-statements", "ss06-24---critical-third-parties"),
    ("supervisory-statements", "ss07-13---definition-of-capital"),
    ("supervisory-statements", "ss07-14---the-use-of-reports-by-skilled-persons"),
    ("supervisory-statements", "ss07-15---solvency-ii-firms-in-difficulty-or-run-off"),
    ("supervisory-statements", "ss07-16---contractual-recognition-of-bail-in"),
    ("supervisory-statements", "ss07-17---solvency-ii-data-collection-of-market-risk-sensitivities"),
    ("supervisory-statements", "ss07-18---solvency-ii-matching-adjustment"),
    ("supervisory-statements", "ss07-24---the-use-of-reports-by-skilled-persons-appointed-in-connection-with-critical-third-parties"),
    ("supervisory-statements", "ss08-14---solvency-ii-recalculation-of-the-transitional-measure-on-technical-provisions-under-solvency-ii"),
    ("supervisory-statements", "ss08-15---solvency-ii-composites"),
    ("supervisory-statements", "ss08-16---ring-fenced-bodies-rfbs"),
    ("supervisory-statements", "ss08-17---solvency-ii-authorisation-and-supervision-of-insurance-special-purpose-vehicles"),
    ("supervisory-statements", "ss08-18---solvency-ii-matching-adjustment---illiquid-unrated-assets-and-equity-release-mortgages"),
    ("supervisory-statements", "ss08-24---the-calculation-of-technical-provisions"),
    ("supervisory-statements", "ss09-13---securitisation-significant-risk-transfer"),
    ("supervisory-statements", "ss09-14---solvency-ii-risk-of-firms-exposure-to-movements-in-market-value"),
    ("supervisory-statements", "ss09-15---solvency-ii-group-supervision"),
    ("supervisory-statements", "ss09-17---recovery-planning"),
    ("supervisory-statements", "ss09-18---solvency-ii-insurance-risk-in-internal-models-relating-to-the-matching-adjustment-and-the-volatility-adjustment"),
    # Statements of Policy
    ("statements-of-policy", "sop01-13---the-pras-approach-to-the-designation-of-investment-firms"),
    ("statements-of-policy", "sop01-14---the-pras-power-to-require-information-from-a-firm-for-financial-stability-purposes"),
    ("statements-of-policy", "sop01-15---the-deposit-guarantee-scheme"),
    ("statements-of-policy", "sop01-16---the-identification-of-other-systemically-important-institutions-o-siis"),
    ("statements-of-policy", "sop01-18---pillar-2-liquidity"),
    ("statements-of-policy", "sop01-19---interpretation-of-eu-guidelines-and-recommendations-bank-of-england-and-pra-approach-after-the-uks-withdrawal-from-the-eu"),
    ("statements-of-policy", "sop01-20---the-publication-by-the-pra-of-solvency-ii-technical-information"),
    ("statements-of-policy", "sop01-21---the-pras-approach-to-the-supervision-of-operational-resilience"),
    ("statements-of-policy", "sop01-22---trading-activity-wind-down"),
    ("statements-of-policy", "sop01-23---the-pras-approach-to-the-notification-of-affected-persons-in-circumstances-where-an-insurer-is-in-financial-difficulties"),
    ("statements-of-policy", "sop01-24---the-pras-approach-to-the-allocation-of-decision-making"),
    ("statements-of-policy", "sop01-25---the-pras-approach-to-policy"),
    ("statements-of-policy", "sop10-24---the-pras-approach-to-insurance-own-funds-permissions"),
    ("statements-of-policy", "sop11-24---the-pras-approach-to-adapting-the-standard-formula"),
    ("statements-of-policy", "sop12-24---the-pras-approach-to-the-scr-recovery-period"),
    ("statements-of-policy", "sop13-24---the-pras-approach-to-volatility-adjustment-permissions"),
    ("statements-of-policy", "sop14-24---the-pras-approach-to-cost-benefit-analysis"),
    ("statements-of-policy", "sop02-13---the-pras-approach-to-giving-a-direction-under-section-316a-of-fsma-in-respect-of-a-qualifying-parent-undertaking"),
    ("statements-of-policy", "sop02-14---the-pras-approach-to-enforcement-statutory-statements-of-policy-and-procedure"),
    ("statements-of-policy", "sop02-15---the-pras-approach-to-the-protection-of-policyholders-in-a-changing-market"),
    ("statements-of-policy", "sop02-16---the-implementation-of-ring-fencing-the-pras-approach-to-ring-fencing-transfer-schemes"),
    ("statements-of-policy", "sop02-21---the-pras-approach-to-the-implementation-of-financial-holding-company-approval-and-direction-making-powers"),
    ("statements-of-policy", "sop02-23---the-pras-approach-to-the-operation-of-the-sddt-regime"),
    ("statements-of-policy", "sop02-24---the-pras-approach-to-transitional-measures-permissions"),
    ("statements-of-policy", "sop02-25---the-pras-approach-to-g-sii-identification-and-g-sii-buffer"),
    ("statements-of-policy", "sop03-13---the-pras-approach-to-enforcement"),
    ("statements-of-policy", "sop03-15---the-pras-approach-to-insurance-business-transfers"),
    ("statements-of-policy", "sop03-16---the-approach-of-pra-and-fca-to-setting-the-deposit-guarantee-scheme-risk-based-levies"),
    ("statements-of-policy", "sop03-21---the-pras-approach-to-granting-liquidity-and-funding-permissions-and-waivers"),
    ("statements-of-policy", "sop03-23---the-pras-approach-to-the-interim-capital-regime-icr"),
    ("statements-of-policy", "sop03-24---the-pras-approach-to-internal-models-permissions"),
    ("statements-of-policy", "sop03-25---the-pras-approach-to-own-funds-waivers-and-permissions"),
    ("statements-of-policy", "sop04-15---the-pras-approach-to-identifying-other-systemically-important-institutions-o-siis-and-calibrating-the-o-sii-buffer"),
    ("statements-of-policy", "sop04-16---the-minimum-requirement-for-own-funds-and-eligible-liabilities-mrel"),
    ("statements-of-policy", "sop04-24---the-pras-approach-to-capital-add-ons"),
    ("statements-of-policy", "sop04-25---solvency-ii-insurance-special-purpose-vehicles---authorisation-and-supervision"),
    ("statements-of-policy", "sop05-15---the-pras-methodologies-for-setting-pillar-2-capital"),
    ("statements-of-policy", "sop05-24---the-pras-approach-to-insurance-group-supervision"),
    ("statements-of-policy", "sop06-24---the-pras-approach-to-waivers-relating-to-regulatory-reporting"),
    ("statements-of-policy", "sop07-24---the-pras-approach-to-insurance-branch-authorisation-and-supervision"),
    ("statements-of-policy", "sop08-24---the-pras-approach-to-matching-adjustment-permissions"),
    ("statements-of-policy", "sop09-24---the-pras-approach-to-rule-permissions-and-waivers"),
]


# ─── Helper Functions ────────────────────────────────────────────────────────

def clean_text(text):
    """Remove noise patterns and clean whitespace from text."""
    if not text:
        return ""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove leading/trailing whitespace from lines
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def clean_html_content(soup):
    """Remove noise elements from BeautifulSoup parsed HTML."""
    # Remove script and style elements
    for tag in soup.find_all(['script', 'style', 'noscript', 'iframe']):
        tag.decompose()

    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove navigation, footer, header, cookie banners
    for selector in [
        'nav', 'footer', 'header',
        '.cookie-banner', '.cookie-consent', '#cookie-banner',
        '.share-buttons', '.social-share', '.email-share',
        '.print-button', '.pdf-button', '.export-buttons',
        '.breadcrumb', '.breadcrumbs',
        '.sidebar-nav', '.side-navigation',
        '#navigation', '.navigation',
        '.back-to-top',
        '[class*="cookie"]', '[class*="Cookie"]',
        '[class*="share"]', '[class*="Share"]',
        '[class*="print"]', '[class*="Print"]',
        '[class*="email"]', '[class*="Email"]',
        '[class*="pdf-export"]', '[class*="convert"]',
        '[class*="toolbar"]', '[class*="Toolbar"]',
        '.document-actions', '.page-actions',
        '.subscribe', '.newsletter',
        '[class*="history"]', '[class*="History"]',
        '[class*="export"]', '[class*="Export"]',
        '[class*="date-picker"]', '[class*="datepicker"]',
    ]:
        for el in soup.select(selector):
            el.decompose()

    # Remove links that are action buttons (email, print, pdf, history, legal instruments inline)
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text(strip=True).lower()
        if any(kw in text for kw in ['email', 'print', 'convert to pdf', 'pdf', 'subscribe']):
            if not any(kw in text for kw in ['policy', 'statement', 'rule', 'chapter']):
                a.decompose()
        elif href.startswith('mailto:') or href.startswith('javascript:'):
            a.decompose()
        elif 'view rulebook as at' in text:
            parent = a.parent
            a.decompose()
            # Also remove parent if it's now empty
            if parent and not parent.get_text(strip=True):
                parent.decompose()

    # Remove buttons
    for btn in soup.find_all('button'):
        btn.decompose()

    # Remove SMALL elements (headings, short divs) containing noise text
    noise_exact = [
        'you are viewing the rulebook',
        'show history',
        'previous history date',
        'next history date',
        'export as',
        'export chapter as',
        'export part as',
        'content loading',
        'show more about this application provision',
        'close',
        'back to top',
    ]
    # Only target headings and short elements - NOT large container divs
    for el in soup.find_all(['span', 'p', 'h2', 'h3', 'h4']):
        text = el.get_text(strip=True).lower()
        if len(text) < 200:  # Only short text elements
            if any(text == noise or text.startswith(noise) for noise in noise_exact):
                el.decompose()

    # Remove the nav-sticky date selector div specifically
    for el in soup.find_all('div', class_='nav-sticky'):
        el.decompose()

    # Remove the col3 sidebar (metadata, not content)
    for el in soup.find_all('div', class_='col3'):
        parent = el.parent
        if parent and 'chapters' in ' '.join(parent.get('class', [])):
            el.decompose()

    # Remove "Legal Instruments that change this rule/chapter" links and their containers
    for a in soup.find_all('a', href=re.compile(r'/legal-instruments\?')):
        text = a.get_text(strip=True).lower()
        if 'legal instruments that change' in text:
            li = a.find_parent('li')
            if li:
                li.decompose()
            else:
                a.decompose()

    # Remove "Related links to this Part" section
    for el in soup.find_all(['h2', 'h3']):
        text = el.get_text(strip=True).lower()
        if 'related links' in text:
            # Remove the heading and its following sibling content
            next_sib = el.find_next_sibling()
            el.decompose()
            if next_sib and next_sib.name in ['ul', 'ol', 'div']:
                next_sib.decompose()

    # Remove "Application Provision" with "show more" noise
    for el in soup.find_all(['h2', 'h3']):
        text = el.get_text(strip=True).lower()
        if text == 'application provision':
            el.decompose()

    # Remove "Glossary" section headers that are navigation, not content
    for el in soup.find_all(['h3']):
        text = el.get_text(strip=True).lower()
        if text == 'glossary' or text == 'guidance' or text == 'policy statements':
            el.decompose()

    # Remove empty list items and empty lists
    for li in soup.find_all('li'):
        if not li.get_text(strip=True):
            li.decompose()
    for ul in soup.find_all(['ul', 'ol']):
        if not ul.get_text(strip=True):
            ul.decompose()

    return soup


def fetch_page(url, retries=3):
    """Fetch a page with retries and rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY)
            resp = SESSION.get(url, timeout=30)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 404:
                print(f"  [404] Not found: {url}")
                return None
            elif resp.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"  [429] Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [{resp.status_code}] Error for {url}")
                if attempt < retries - 1:
                    time.sleep(2)
        except requests.RequestException as e:
            print(f"  [ERR] {e}")
            if attempt < retries - 1:
                time.sleep(3)
    return None


def extract_metadata(soup, url, content_type="rule"):
    """Extract metadata from a PRA page."""
    metadata = {
        "source_url": url,
        "content_type": content_type,
        "scrape_date": datetime.now().isoformat(),
        "as_at_date": DATE_PARAM,
        "title": "",
        "chapters": [],
        "applies_to": [],
        "related_guidance": [],
        "related_policy_statements": [],
        "related_legal_instruments": [],
    }

    # Title
    title_el = soup.find('h1') or soup.find('title')
    if title_el:
        title_text = title_el.get_text(strip=True)
        # Clean PRA Rulebook prefix from title
        title_text = re.sub(r'^PRA Rulebook\s*[-–]\s*', '', title_text)
        metadata["title"] = clean_text(title_text)

    # Extract from sidebar (col3) for metadata
    sidebar = None
    chapters_container = soup.find('div', class_='chapters')
    if chapters_container:
        sidebar = chapters_container.find('div', class_='col3')

    if sidebar:
        # "Used in" = applies to which firm types
        used_in = sidebar.find('h2', string=re.compile(r'(?i)used in'))
        if used_in:
            ul = used_in.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    text = li.get_text(strip=True)
                    if text and 'legal instrument' not in text.lower():
                        metadata["applies_to"].append(text)

        # Related guidance
        for a in sidebar.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if '/guidance/' in href and text:
                metadata["related_guidance"].append({"title": text, "url": href})
            elif 'bankofengland.co.uk' in href and text:
                metadata["related_policy_statements"].append({"title": text, "url": href})

    # Find chapter headings from the main content area
    main_content = None
    if chapters_container:
        main_content = chapters_container.find('div', class_='col9')

    if main_content:
        noise_headings = {'glossary', 'export as', 'export chapter as', 'export part as',
                          'close', 'used in', 'related links', 'guidance',
                          'policy statements', 'application provision'}
        for heading in main_content.find_all(['h3']):
            text = heading.get_text(strip=True)
            if text and len(text) > 2:
                text_lower = text.lower().strip()
                if not any(text_lower.startswith(n) for n in noise_headings):
                    if 'you are viewing' not in text_lower and 'show history' not in text_lower:
                        metadata["chapters"].append(text)

    return metadata


def extract_main_content(soup):
    """Extract the main content area, excluding navigation and noise."""
    # PRA Rulebook specific: content is in div.col9 inside div.container.chapters
    chapters_container = soup.find('div', class_='chapters')
    if chapters_container:
        col9 = chapters_container.find('div', class_='col9')
        if col9:
            return col9

    # For guidance pages, try different structure
    # Look for the main body/article content
    for selector in [
        ('div', {'class': 'document-content'}),
        ('div', {'class': 'guidance-content'}),
        ('div', {'class': 'ss-content'}),
        ('article', {}),
        ('main', {}),
    ]:
        el = soup.find(selector[0], selector[1]) if selector[1] else soup.find(selector[0])
        if el:
            return el

    # Fallback: find the largest text content div
    main = (
        soup.find('div', class_=re.compile(r'(?i)content|main|article|body')) or
        soup.find('article') or
        soup.find('main') or
        soup.find('div', id=re.compile(r'(?i)content|main'))
    )
    return main if main else soup.find('body') or soup


def html_to_clean_markdown(html_content):
    """Convert HTML to clean markdown."""
    h2t = html2text.HTML2Text()
    h2t.ignore_links = False
    h2t.ignore_images = True
    h2t.ignore_emphasis = False
    h2t.body_width = 0  # No wrapping
    h2t.unicode_snob = True
    md = h2t.handle(str(html_content))
    md = clean_text(md)

    # Post-process markdown to remove remaining noise lines
    noise_line_patterns = [
        r'^#+\s*Export\s+(as|chapter)',
        r'^#+\s*Glossary\s*$',
        r'^#+\s*Close\s*$',
        r'^#+\s*Used in\s*$',
        r'^#+\s*Related links',
        r'^#+\s*Guidance\s*$',
        r'^#+\s*Policy Statements\s*$',
        r'^#+\s*Application Provision\s*$',
        r'^\s*Content loading\s*$',
        r'^\s*Show more\s+about',
        r'^\s*Previous history date',
        r'^\s*Next history date',
        r'^#+\s*You are viewing',
        r'^\s*View Rulebook as at',
        r'^\s*\*\s*\*\s*\*\s*$',  # Horizontal rules (*** ) that are separators
        r'^\s*Legal Instruments that change',
        r'^\[?\s*CRR Firms\s*\]',
        r'^\[?\s*Non-CRR Firms\s*\]',
        r'^\[?\s*SII Firms\s*\]',
        r'^\[?\s*Non-SII Firms\s*\]',
        r'^\[?\s*Non-authorised\s*\]',
    ]

    lines = md.split('\n')
    cleaned_lines = []
    skip_block = False

    for line in lines:
        stripped = line.strip()

        # Skip "Related links" block until next major heading
        if skip_block:
            if re.match(r'^#{1,2}\s+\d', stripped) or re.match(r'^\d+\.\d+', stripped):
                skip_block = False
            else:
                continue

        if re.match(r'^#+\s*Related links', stripped, re.IGNORECASE):
            skip_block = True
            continue

        # Skip "Used in" block
        if re.match(r'^#+\s*Used in', stripped, re.IGNORECASE):
            skip_block = True
            continue

        # Skip individual noise lines
        should_skip = False
        for pattern in noise_line_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                should_skip = True
                break

        if should_skip:
            continue

        # Remove inline legal instrument references
        line = re.sub(r'\[\s*Legal Instruments that change[^\]]*\]\([^\)]*\)', '', line)
        # Preserve inline effective dates but format them as metadata
        date_only_match = re.match(r'^\s*\*?\s*(\d{2}/\d{2}/\d{4})\s*$', line)
        if date_only_match:
            line = f"*Effective: {date_only_match.group(1)}*"
        # Remove "Past version of X.X before" links
        line = re.sub(r'\[\s*Past\s+version of[^\]]*\]\([^\)]*\)', '', line)
        # Remove standalone past version bullets
        if re.match(r'^\s*\*\s*\[\s*Past\s+version', line):
            continue
        # Remove "View Rulebook" links
        line = re.sub(r'\[\s*View Rulebook[^\]]*\]\([^\)]*\)', '', line)
        # Remove empty bullet points (residual from link removal)
        if re.match(r'^\s*\*\s*$', line.strip()):
            continue
        if re.match(r'^\s*\*\s+$', line):
            continue

        cleaned_lines.append(line)

    md = '\n'.join(cleaned_lines)
    # Collapse multiple blank lines
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


def build_clean_html(title, content_html, metadata):
    """Build a clean standalone HTML document."""
    meta_html = ""
    if metadata.get("as_at_date"):
        meta_html += f'<p class="meta"><strong>Effective Date:</strong> {metadata["as_at_date"]}</p>\n'
    if metadata.get("source_url"):
        meta_html += f'<p class="meta"><strong>Source:</strong> <a href="{metadata["source_url"]}">{metadata["source_url"]}</a></p>\n'
    if metadata.get("content_type"):
        meta_html += f'<p class="meta"><strong>Type:</strong> {metadata["content_type"]}</p>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_module.escape(title)} - PRA Rulebook</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
        h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
        h2 {{ color: #283593; margin-top: 30px; }}
        h3 {{ color: #3949ab; }}
        .meta {{ color: #666; font-size: 0.9em; margin: 2px 0; }}
        .metadata-block {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 30px; border-left: 4px solid #1a237e; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #e8eaf6; }}
        .rule-text {{ background: #fafafa; padding: 10px; border-left: 3px solid #7986cb; margin: 10px 0; }}
        a {{ color: #1565c0; }}
    </style>
</head>
<body>
    <h1>{html_module.escape(title)}</h1>
    <div class="metadata-block">
        {meta_html}
        <p class="meta"><strong>Scraped:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
    <div class="content">
        {content_html}
    </div>
</body>
</html>"""


def sanitize_for_pdf(text):
    """Sanitize text for PDF output using latin-1 compatible characters."""
    if not text:
        return ""
    # Replace common Unicode characters with latin-1 equivalents
    replacements = {
        '\u2013': '-',   # en-dash
        '\u2014': '--',  # em-dash
        '\u2018': "'",   # left single quote
        '\u2019': "'",   # right single quote
        '\u201c': '"',   # left double quote
        '\u201d': '"',   # right double quote
        '\u2026': '...', # ellipsis
        '\u00a0': ' ',   # non-breaking space
        '\u2022': '*',   # bullet
        '\u2023': '>',   # triangle bullet
        '\u2027': '-',   # hyphenation point
        '\u00b7': '*',   # middle dot
        '\u2032': "'",   # prime
        '\u2033': '"',   # double prime
        '\u2039': '<',   # single left angle quote
        '\u203a': '>',   # single right angle quote
        '\u00ab': '<<',  # left double angle quote
        '\u00bb': '>>',  # right double angle quote
        '\u200b': '',    # zero-width space
        '\u200c': '',    # zero-width non-joiner
        '\u200d': '',    # zero-width joiner
        '\ufeff': '',    # BOM
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Final fallback: encode to latin-1 with replace
    return text.encode('latin-1', errors='replace').decode('latin-1')


class PdfWriter(FPDF):
    """Custom PDF writer with proper Unicode support."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        # Use built-in Helvetica (no need for external fonts)
        self.alias_nb_pages()

    def header(self):
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'PRA Rulebook - Bank of England', 0, 0, 'L')
        self.cell(0, 5, f'Effective: {DATE_PARAM}', 0, 1, 'R')
        self.line(10, 12, 200, 12)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def add_title(self, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(26, 35, 126)
        safe = sanitize_for_pdf(title)
        self.multi_cell(0, 10, safe)
        self.ln(3)
        self.set_draw_color(26, 35, 126)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)

    def add_metadata(self, metadata):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(100, 100, 100)
        items = [
            f"Source: {metadata.get('source_url', 'N/A')}",
            f"Effective Date: {metadata.get('as_at_date', 'N/A')}",
            f"Type: {metadata.get('content_type', 'N/A')}",
            f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        for item in items:
            safe = sanitize_for_pdf(item)
            self.cell(0, 5, safe, 0, 1)
        self.ln(5)

    def add_body_text(self, text):
        """Add body text with basic formatting from markdown."""
        self.set_text_color(51, 51, 51)
        lines = text.split('\n')
        for line in lines:
            stripped = line.strip()
            if not stripped:
                self.ln(3)
                continue

            # Headings
            if stripped.startswith('### '):
                self.set_font('Helvetica', 'B', 11)
                self.set_text_color(57, 73, 171)
                safe = sanitize_for_pdf(stripped[4:])
                self.multi_cell(0, 6, safe)
                self.ln(2)
            elif stripped.startswith('## '):
                self.set_font('Helvetica', 'B', 13)
                self.set_text_color(40, 53, 147)
                safe = sanitize_for_pdf(stripped[3:])
                self.multi_cell(0, 7, safe)
                self.ln(3)
            elif stripped.startswith('# '):
                self.set_font('Helvetica', 'B', 14)
                self.set_text_color(26, 35, 126)
                safe = sanitize_for_pdf(stripped[2:])
                self.multi_cell(0, 8, safe)
                self.ln(3)
            else:
                self.set_font('Helvetica', '', 10)
                self.set_text_color(51, 51, 51)
                # Remove markdown bold/italic markers for PDF
                clean = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
                clean = re.sub(r'\*(.+?)\*', r'\1', clean)
                clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)  # Remove links
                safe = sanitize_for_pdf(clean)
                self.multi_cell(0, 5, safe)
                self.ln(1)


def save_outputs(slug, title, content_html, markdown_text, metadata, category):
    """Save content in all four formats."""
    safe_slug = re.sub(r'[^\w\-]', '_', slug)

    # 1. JSON
    json_path = OUTPUT_DIR / "json" / category / f"{safe_slug}.json"
    json_data = {
        "metadata": metadata,
        "title": title,
        "content_markdown": markdown_text,
        "content_html": str(content_html),
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    # 2. Markdown
    md_path = OUTPUT_DIR / "md" / category / f"{safe_slug}.md"
    md_header = f"""---
title: "{title}"
source: "{metadata.get('source_url', '')}"
as_at_date: "{metadata.get('as_at_date', '')}"
content_type: "{metadata.get('content_type', '')}"
scrape_date: "{metadata.get('scrape_date', '')}"
---

# {title}

"""
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_header + markdown_text)

    # 3. HTML
    html_path = OUTPUT_DIR / "html" / category / f"{safe_slug}.html"
    full_html = build_clean_html(title, str(content_html), metadata)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    # 4. PDF
    pdf_path = OUTPUT_DIR / "pdf" / category / f"{safe_slug}.pdf"
    try:
        pdf = PdfWriter()
        pdf.add_page()
        pdf.add_title(title)
        pdf.add_metadata(metadata)
        pdf.add_body_text(markdown_text)
        pdf.output(str(pdf_path))
    except Exception as e:
        print(f"  [PDF ERR] {safe_slug}: {e}")
        traceback.print_exc()


# ─── Scrapers ────────────────────────────────────────────────────────────────

def scrape_rules():
    """Scrape all PRA Rules pages."""
    print(f"\n{'='*60}")
    print("SCRAPING PRA RULES")
    print(f"{'='*60}")
    total = len(RULES_SLUGS)
    success = 0
    failed = []

    for i, slug in enumerate(RULES_SLUGS, 1):
        url = f"{BASE_URL}/pra-rules/{slug}/{DATE_PARAM}"
        print(f"[{i}/{total}] {slug}...")

        resp = fetch_page(url)
        if not resp:
            failed.append(slug)
            continue

        # Parse twice: once for metadata (before cleaning), once for content
        soup_meta = BeautifulSoup(resp.text, 'html.parser')
        metadata = extract_metadata(soup_meta, url, "PRA Rule")

        soup = BeautifulSoup(resp.text, 'html.parser')
        soup = clean_html_content(soup)
        main_content = extract_main_content(soup)
        content_html = main_content
        markdown_text = html_to_clean_markdown(str(content_html))
        title = metadata.get("title") or slug.replace('-', ' ').title()

        save_outputs(slug, title, content_html, markdown_text, metadata, "rules")
        success += 1
        print(f"  -> OK: {title}")

    print(f"\nRules complete: {success}/{total} succeeded, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")
    return success, failed


def scrape_guidance():
    """Scrape all PRA Guidance pages."""
    print(f"\n{'='*60}")
    print("SCRAPING PRA GUIDANCE")
    print(f"{'='*60}")
    total = len(GUIDANCE_SLUGS)
    success = 0
    failed = []

    for i, (gtype, slug) in enumerate(GUIDANCE_SLUGS, 1):
        url = f"{BASE_URL}/guidance/{gtype}/{slug}/{DATE_PARAM}"
        print(f"[{i}/{total}] {slug}...")

        resp = fetch_page(url)
        if not resp:
            failed.append(slug)
            continue

        content_type = "Supervisory Statement" if gtype == "supervisory-statements" else "Statement of Policy"

        # Parse twice: once for metadata, once for cleaned content
        soup_meta = BeautifulSoup(resp.text, 'html.parser')
        metadata = extract_metadata(soup_meta, url, content_type)

        soup = BeautifulSoup(resp.text, 'html.parser')
        soup = clean_html_content(soup)
        main_content = extract_main_content(soup)
        content_html = main_content
        markdown_text = html_to_clean_markdown(str(content_html))
        title = metadata.get("title") or slug.replace('-', ' ').title()

        save_outputs(slug, title, content_html, markdown_text, metadata, "guidance")
        success += 1
        print(f"  -> OK: {title}")

    print(f"\nGuidance complete: {success}/{total} succeeded, {len(failed)} failed")
    if failed:
        print(f"Failed: {failed}")
    return success, failed


def scrape_glossary():
    """Scrape the PRA Glossary."""
    print(f"\n{'='*60}")
    print("SCRAPING PRA GLOSSARY")
    print(f"{'='*60}")

    all_terms = []

    # Fetch all terms at once using AZ=All&NoPage=1
    url = f"{BASE_URL}/glossary?Date={DATE_PARAM}&AZ=All&NoPage=1"
    print(f"Fetching complete glossary (all terms)...")
    resp = fetch_page(url)

    if resp:
        soup = BeautifulSoup(resp.text, 'html.parser')

        # PRA glossary structure:
        # ul.glossary-results > li > div.accordion-head > h3 > button.accordion-button = term name
        # Same li > div.accordion-content > div.glossary-box-links-container > div.glossary-result-content > p = definition
        glossary_list = soup.find('ul', class_='glossary-results')
        if glossary_list:
            items = glossary_list.find_all('li', recursive=False)
            print(f"  Found {len(items)} glossary items")

            for item in items:
                # Get term name from accordion button
                btn = item.find('button', class_='accordion-button')
                if not btn:
                    continue
                # Remove the accordion-toggle span to get clean term name
                toggle = btn.find('span', class_='accordion-toggle')
                if toggle:
                    toggle.decompose()
                term_name = btn.get_text(strip=True)

                # Get definition from glossary-result-content
                content_div = item.find('div', class_='glossary-result-content')
                if content_div:
                    definition = content_div.get_text(strip=True)
                else:
                    definition = ""

                # Get effective date from list-links
                eff_date = ""
                links_items = item.find_all('li', class_='list-links__item')
                for li in links_items:
                    text = li.get_text(strip=True)
                    if re.match(r'\d{2}/\d{2}/\d{4}', text):
                        eff_date = text
                        break

                if term_name and definition:
                    all_terms.append({
                        "term": term_name,
                        "definition": clean_text(definition),
                        "as_at_date": eff_date,
                    })
        else:
            print("  WARNING: Could not find glossary-results list")
            # Fallback: try extract_glossary_terms
            terms = extract_glossary_terms(soup)
            if terms:
                all_terms.extend(terms)

    # Deduplicate
    seen = set()
    unique_terms = []
    for term in all_terms:
        if term['term'] not in seen:
            seen.add(term['term'])
            unique_terms.append(term)
    all_terms = sorted(unique_terms, key=lambda t: t['term'].lower())

    print(f"\nTotal glossary terms collected: {len(all_terms)}")

    if all_terms:
        # Save glossary outputs
        metadata = {
            "source_url": f"{BASE_URL}/glossary?Date={DATE_PARAM}",
            "content_type": "Glossary",
            "scrape_date": datetime.now().isoformat(),
            "as_at_date": DATE_PARAM,
            "title": "PRA Rulebook Glossary",
            "total_terms": len(all_terms),
        }

        # Build content
        markdown_lines = ["# PRA Rulebook Glossary\n"]
        html_lines = ["<h1>PRA Rulebook Glossary</h1>\n<dl>\n"]

        for term in all_terms:
            markdown_lines.append(f"## {term['term']}\n")
            markdown_lines.append(f"{term['definition']}\n")
            if term.get('as_at_date'):
                markdown_lines.append(f"*Effective: {term['as_at_date']}*\n")
            markdown_lines.append("")

            html_lines.append(f'  <dt><strong>{html_module.escape(term["term"])}</strong></dt>\n')
            html_lines.append(f'  <dd>{html_module.escape(term["definition"])}')
            if term.get('as_at_date'):
                html_lines.append(f' <em>(Effective: {term["as_at_date"]})</em>')
            html_lines.append('</dd>\n')

        html_lines.append("</dl>")

        markdown_text = '\n'.join(markdown_lines)
        content_html = '\n'.join(html_lines)

        # Save per-letter files and combined
        save_outputs("pra-glossary-complete", "PRA Rulebook Glossary",
                     content_html, markdown_text, metadata, "glossary")

        # Also save individual letter files
        for letter in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            letter_terms = [t for t in all_terms if t['term'].upper().startswith(letter)]
            if letter_terms:
                letter_md = [f"# PRA Glossary - {letter}\n"]
                letter_html_lines = [f"<h1>PRA Glossary - {letter}</h1>\n<dl>\n"]
                for term in letter_terms:
                    letter_md.append(f"## {term['term']}\n\n{term['definition']}\n")
                    letter_html_lines.append(f'  <dt><strong>{html_module.escape(term["term"])}</strong></dt>\n')
                    letter_html_lines.append(f'  <dd>{html_module.escape(term["definition"])}</dd>\n')
                letter_html_lines.append("</dl>")

                letter_metadata = {**metadata, "title": f"PRA Glossary - {letter}", "total_terms": len(letter_terms)}
                save_outputs(f"glossary-{letter.lower()}", f"PRA Glossary - {letter}",
                             '\n'.join(letter_html_lines), '\n'.join(letter_md),
                             letter_metadata, "glossary")

        # JSON with structured terms
        json_path = OUTPUT_DIR / "json" / "glossary" / "pra-glossary-structured.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": metadata,
                "terms": all_terms
            }, f, indent=2, ensure_ascii=False)

    return len(all_terms)


def extract_glossary_terms(soup):
    """Extract glossary terms from a BeautifulSoup parsed glossary page."""
    terms = []

    # Strategy 1: Look for definition list <dl><dt><dd>
    for dt in soup.find_all('dt'):
        dd = dt.find_next_sibling('dd')
        if dd:
            term_name = dt.get_text(strip=True)
            definition = dd.get_text(strip=True)
            if term_name and definition:
                terms.append({
                    "term": term_name,
                    "definition": clean_text(definition),
                    "as_at_date": "",
                })

    if terms:
        return terms

    # Strategy 2: Look for table rows
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                term_name = cells[0].get_text(strip=True)
                definition = cells[1].get_text(strip=True)
                eff_date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                if term_name and definition and term_name.lower() not in ['term', 'definition', 'name']:
                    terms.append({
                        "term": term_name,
                        "definition": clean_text(definition),
                        "as_at_date": eff_date,
                    })

    if terms:
        return terms

    # Strategy 3: Look for divs with term/definition pattern
    for div in soup.find_all('div', class_=re.compile(r'(?i)glossary|term|definition')):
        heading = div.find(['h2', 'h3', 'h4', 'strong', 'b'])
        if heading:
            term_name = heading.get_text(strip=True)
            # Get remaining text as definition
            heading.decompose()
            definition = div.get_text(strip=True)
            if term_name and definition:
                terms.append({
                    "term": term_name,
                    "definition": clean_text(definition),
                    "as_at_date": "",
                })

    # Strategy 4: Parse from sections with bold terms followed by text
    if not terms:
        for strong in soup.find_all(['strong', 'b']):
            parent = strong.parent
            if parent:
                term_name = strong.get_text(strip=True)
                strong.decompose()
                definition = parent.get_text(strip=True)
                if term_name and definition and len(definition) > 10:
                    terms.append({
                        "term": term_name,
                        "definition": clean_text(definition),
                        "as_at_date": "",
                    })

    return terms


# ─── Dynamic URL Discovery ──────────────────────────────────────────────────

def discover_guidance_urls():
    """Discover all guidance URLs from the main guidance page."""
    print("Discovering guidance URLs from index page...")
    url = f"{BASE_URL}/guidance"
    resp = fetch_page(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    discovered = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/guidance/' in href and DATE_PARAM in href:
            # Parse out the type and slug
            parts = href.strip('/').split('/')
            if len(parts) >= 3:
                gtype = parts[1] if 'guidance' in parts[0] else parts[2]
                slug = parts[2] if 'guidance' in parts[0] else parts[3] if len(parts) > 3 else ""
                if gtype in ['supervisory-statements', 'statements-of-policy'] and slug:
                    # Remove date suffix from slug if present
                    slug = slug.replace(f'/{DATE_PARAM}', '')
                    discovered.append((gtype, slug))

    # Deduplicate
    discovered = list(dict.fromkeys(discovered))
    print(f"  Discovered {len(discovered)} guidance URLs")
    return discovered


def discover_rule_urls():
    """Discover all rule URLs from the main rules page."""
    print("Discovering rule URLs from index page...")
    url = f"{BASE_URL}/pra-rules"
    resp = fetch_page(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    discovered = []

    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/pra-rules/' in href and DATE_PARAM in href:
            parts = href.strip('/').split('/')
            for j, part in enumerate(parts):
                if part == 'pra-rules' and j + 1 < len(parts):
                    slug = parts[j + 1]
                    if slug != DATE_PARAM and slug != 'forms':
                        discovered.append(slug)
                    break

    # Deduplicate
    discovered = list(dict.fromkeys(discovered))
    print(f"  Discovered {len(discovered)} rule URLs")
    return discovered


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    print("=" * 60)
    print("PRA RULEBOOK SCRAPER")
    print(f"Date: {DATE_PARAM}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    # Discover additional URLs from index pages
    print("\n--- Phase 1: URL Discovery ---")
    discovered_rules = discover_rule_urls()
    discovered_guidance = discover_guidance_urls()

    # Merge discovered URLs with hardcoded ones
    global RULES_SLUGS, GUIDANCE_SLUGS
    existing_rules = set(RULES_SLUGS)
    for slug in discovered_rules:
        if slug not in existing_rules:
            RULES_SLUGS.append(slug)
            existing_rules.add(slug)

    existing_guidance = set((g, s) for g, s in GUIDANCE_SLUGS)
    for gtype, slug in discovered_guidance:
        if (gtype, slug) not in existing_guidance:
            GUIDANCE_SLUGS.append((gtype, slug))
            existing_guidance.add((gtype, slug))

    print(f"\nTotal rules to scrape: {len(RULES_SLUGS)}")
    print(f"Total guidance to scrape: {len(GUIDANCE_SLUGS)}")

    # Phase 2: Scrape Rules
    print("\n--- Phase 2: Scraping Rules ---")
    rules_success, rules_failed = scrape_rules()

    # Phase 3: Scrape Guidance
    print("\n--- Phase 3: Scraping Guidance ---")
    guidance_success, guidance_failed = scrape_guidance()

    # Phase 4: Scrape Glossary
    print("\n--- Phase 4: Scraping Glossary ---")
    glossary_count = scrape_glossary()

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print("SCRAPE COMPLETE")
    print(f"{'='*60}")
    print(f"Rules:    {rules_success} scraped, {len(rules_failed)} failed")
    print(f"Guidance: {guidance_success} scraped, {len(guidance_failed)} failed")
    print(f"Glossary: {glossary_count} terms")
    print(f"Time:     {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"\nOutput directories:")
    for fmt in ['pdf', 'json', 'md', 'html']:
        for cat in ['rules', 'guidance', 'glossary']:
            p = OUTPUT_DIR / fmt / cat
            count = len(list(p.glob('*'))) if p.exists() else 0
            print(f"  {fmt}/{cat}: {count} files")


if __name__ == "__main__":
    main()
