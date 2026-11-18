"""Task 14 fetch step: processes the 7 sources verified in proposed_sources.json using
task14_pipeline.py's ported extraction/chunking functions. Run from research/colab/ with .venv-rag."""

from task14_pipeline import process_pdf_job, process_web_job

PDF_JOBS = [
    {
        "url": "https://gcwus.edu.pk/wp-content/uploads/Paigham-e-Pakistan.pdf",
        "filename": "paigham_e_pakistan_2018.pdf",
        "subject": "Islamic Studies", "topic": "Jihad vs. Terrorism / National Anti-Terrorism Narrative",
        "source_title": "Paigham-e-Pakistan (2018)",
    },
    {
        "url": "https://treaties.un.org/doc/Publication/UNTS/Volume%20560/volume-560-I-8166-English.pdf",
        "filename": "tashkent_declaration_1966.pdf",
        "subject": "International Relations", "topic": "Kashmir Dispute and Bilateral Agreements",
        "source_title": "Tashkent Declaration (1966) -- UN Treaty Series No. 8166",
    },
    {
        "url": "https://pax.peaceagreements.org/media/documents/ag577_56a8f33b402c5.pdf",
        "filename": "lahore_declaration_1999.pdf",
        "subject": "International Relations", "topic": "Kashmir Dispute and Bilateral Agreements",
        "source_title": "The Lahore Declaration (1999)",
    },
]

WEB_JOBS = [
    {
        "url": "https://plato.stanford.edu/entries/sovereignty/",
        "subject": "Political Science", "topic": "Theories of State Sovereignty",
        "source_title": "Sovereignty -- Stanford Encyclopedia of Philosophy",
        "source_type": "academic_reference",
    },
    {
        "url": "https://www.wto.org/english/thewto_e/whatis_e/tif_e/tif_e.htm",
        "subject": "Current Affairs", "topic": "World Trade Organization",
        "source_title": "Understanding the WTO",
        "source_type": "official_document",
    },
    {
        "url": "https://mowr.gov.pk/Detail/NzZkZThlNWItYjczOC00NWY5LTk0ODYtZjJhMjBiYjc3YmZk",
        "subject": "Current Affairs", "topic": "Pakistan Water Resources and IRSA",
        "source_title": "Indus River System Authority (IRSA) -- official detail page",
        "source_type": "official_document",
    },
    {
        "url": "https://sunnah.com/muslim:1218",
        "subject": "Islamic Studies", "topic": "Seerah / Farewell Sermon / Farewell Hajj",
        "source_title": "Sahih Muslim 1218 -- The Prophet's Hajj (Farewell Sermon elements)",
        "source_type": "primary_historical_text",
    },
]

if __name__ == "__main__":
    log = {"success": [], "failed": []}
    for job in PDF_JOBS:
        process_pdf_job(job, log)
    for job in WEB_JOBS:
        process_web_job(job, log)
    print("\n=== Task 14 fetch summary ===")
    print("Succeeded:", len(log["success"]))
    for s in log["success"]:
        print(" OK", s)
    print("Failed:", len(log["failed"]))
    for f in log["failed"]:
        print(" FAIL", f)
