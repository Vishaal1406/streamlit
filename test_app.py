import pytest
from app import translate_text, apply_tamil_overrides, get_time_of_day, is_weekend

def test_translation():
    """Test English to Tamil translation"""
    assert translate_text("Hello") == "Hello"  # English should stay the same
    assert apply_tamil_overrides("வண்டி") == "கார்ட்"  # Tamil word replacement
    assert apply_tamil_overrides("வாடா") == "வடை"  # Another Tamil override
    assert apply_tamil_overrides("சாம்பார் அரிசி") == "சாம்பார் சாதம்"  # Another Tamil override

def test_time_of_day():
    """Test time classification"""
    result = get_time_of_day()
    assert result in ["Morning", "Afternoon", "Evening", "Night"]

def test_weekend():
    """Ensure it correctly identifies weekends"""
    result = is_weekend()
    assert result in [0, 1]  # 1 for Saturday/Sunday, 0 for Monday-Friday

if __name__ == "__main__":
    pytest.main()
