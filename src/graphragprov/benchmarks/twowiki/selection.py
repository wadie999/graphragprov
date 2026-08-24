from graphragprov.benchmarks.twowiki.case import TwoWikiCase
from graphragprov.benchmarks.twowiki.paragraph import TwoWikiParagraph


def supporting_paragraphs(case: TwoWikiCase) -> tuple[TwoWikiParagraph, ...]:
    """Return supporting paragraphs in benchmark evidence order."""

    paragraphs_by_title = {paragraph.title: paragraph for paragraph in case.paragraphs}

    titles: list[str] = []

    for evidence in case.evidences:
        if evidence.subject in paragraphs_by_title and evidence.subject not in titles:
            titles.append(evidence.subject)

    for fact in case.supporting_facts:
        if fact.title not in titles:
            titles.append(fact.title)

    return tuple(paragraphs_by_title[title] for title in titles)
