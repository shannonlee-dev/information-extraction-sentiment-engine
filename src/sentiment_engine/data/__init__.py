"""설치된 패키지에 포함된 사전과 평가 데이터의 위치."""
from importlib.resources import files

LEXICONS = files(__package__).joinpath("lexicons")
EVALUATION = files(__package__).joinpath("evaluation")
