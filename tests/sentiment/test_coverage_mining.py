import pytest

from scripts.mine_sentiment_coverage import mine


@pytest.mark.parametrize('field', ['label', 'rating', 'gold', 'target', 'sentiment', 'polarity'])
def test_miner_rejects_labels_before_analysis(field):
    with pytest.raises(ValueError, match='id/text'):
        mine([{'id': '1', 'text': 'anything', field: 'positive'}], {'1': 'g'})


def test_miner_ranks_distinct_groups_and_does_not_assign_polarity():
    rows = [{'id': '1', 'text': '연필'}, {'id': '2', 'text': '연필'},
            {'id': '3', 'text': '공책'}, {'id': '4', 'text': '공책'}]
    result = mine(rows, {'1': 'g1', '2': 'g1', '3': 'g2', '4': 'g3'})
    terms = {r['morph']: r for r in result['vocabulary']}
    assert terms['공책']['group_frequency'] == 2
    assert terms['연필']['group_frequency'] == 1
    assert all('score' not in r and 'label' not in r for r in result['vocabulary'])
    assert result['vocabulary'][0]['group_frequency'] == 2


def test_miner_requires_complete_group_map():
    with pytest.raises(ValueError, match='group'):
        mine([{'id': '1', 'text': '단어'}], {})


def test_miner_validates_entire_input_before_first_analysis(monkeypatch):
    from scripts import mine_sentiment_coverage as miner
    def forbidden(text):
        raise AssertionError('analysis started before schema validation finished')
    monkeypatch.setattr(miner,'analyze_morphology',forbidden)
    with pytest.raises(ValueError,match='id/text'):
        mine([{'id':'1','text':'valid'},{'id':'2','text':'invalid','label':'negative'}],{'1':'g1','2':'g2'})


def test_miner_separates_derivation_boundaries_and_opaque_tokens():
    rows = [{'id': '1', 'text': '변색된'}, {'id': '2', 'text': '변색된'},
            {'id': '3', 'text': '행복주택'}, {'id': '4', 'text': '이뻐욬'}]
    result = mine(rows, {'1': 'g1', '2': 'g1', '3': 'g2', '4': 'g3'})
    categories = result['unmatched_categories']
    assert categories['known_key_before_derivation']['occurrences'] == 2
    assert categories['known_key_before_derivation']['group_frequency'] == 1
    assert categories['known_key_before_noun_or_suffix']['group_frequency'] == 1
    assert categories['opaque_na']['group_frequency'] == 1
    assert sum(row['occurrences'] for row in categories.values()) == 4
    assert all('label' not in row and 'score' not in row for row in categories.values())
