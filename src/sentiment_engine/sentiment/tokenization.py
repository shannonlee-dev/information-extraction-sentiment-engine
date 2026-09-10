"""사전 표현과 입력 문장에 공통으로 사용하는 토큰화 규칙."""
import re

# 기존 토큰화 규칙: 한글/영문/숫자 어절과 문장부호를 분리한다.
# 줄바꿈도 남겨 두어 부정어·강조어가 다음 문장으로 넘어가지 않게 한다.
TOKEN_PATTERN = re.compile(r'[가-힣A-Za-z0-9]+|[^\w\s]|[\r\n]')


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)
