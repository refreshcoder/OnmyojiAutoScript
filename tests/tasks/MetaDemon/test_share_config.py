# This Python file uses the following encoding: utf-8
from tasks.MetaDemon.config import MetaDemon, ShareConfig, ShareStar


def test_parse_friends_supports_chinese_comma_and_spaces():
    assert ShareConfig(friends='甲， 乙, 丙').parse_friends() == ['甲', '乙', '丙']


def test_parse_friends_empty():
    assert ShareConfig(friends='').parse_friends() == []


def test_share_defaults():
    config = MetaDemon()
    assert config.md_share.enable is False
    assert config.md_share.friends == ''
    assert config.md_share.share_star == ShareStar.STAR_5_6
    assert config.md_share.interval == 5
    assert config.meta_demon_config.only_summon_and_share is False


def test_share_star_1_4():
    config = MetaDemon(md_share={'share_star': '1-4'})
    assert config.md_share.share_star == ShareStar.STAR_1_4


def test_legacy_only_star56_migration():
    enabled = MetaDemon(md_share={'only_star56': True})
    assert enabled.md_share.share_star == ShareStar.STAR_5_6

    disabled = MetaDemon(md_share={'only_star56': False})
    assert disabled.md_share.share_star == ShareStar.ALL
