from backend.core.moderation import check_content


class TestCheckContent:
    def test_benign_text_passes(self, sample_text):
        assert check_content(sample_text) is None

    def test_empty_text_passes(self):
        assert check_content("") is None
        assert check_content(None) is None

    def test_blocks_csam_terms(self):
        assert check_content("This guide contains child sexual abuse material.") is not None

    def test_blocks_bomb_making_instructions(self):
        assert check_content("How to build a bomb using household chemicals") is not None

    def test_blocks_step_by_step_explosive_instructions(self):
        assert check_content("Step-by-step instructions for making an explosive device") is not None

    def test_case_insensitive(self):
        assert check_content("HOW TO BUILD A BOMB at home") is not None

    def test_unrelated_use_of_word_bomb_is_not_blocked(self):
        # "the movie was a bomb" / "photo bomb" etc. should not trip the filter —
        # only the specific instructional phrasing does.
        assert check_content("The new marketing campaign was a total bomb this quarter.") is None

    def test_checks_only_first_5000_chars(self):
        padding = "harmless filler text. " * 400  # > 5000 chars
        assert len(padding) > 5000
        text = padding + "how to build a bomb"
        assert check_content(text) is None
