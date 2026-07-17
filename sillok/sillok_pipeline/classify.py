"""Event-type classification from 실록 title/body text.

Keywords are the stereotyped expressions used in the veritable records
(and their Korean translations). A single article can match multiple types.
"""

EVENT_LEXICON = {
    "붕어": ["훙", "薨", "昇遐", "승하", "崩", "붕어", "禮陟", "훙서", "薨逝"],
    "졸기": ["卒", "졸하", "졸기"],
    "처형": ["伏誅", "복주", "賜死", "사사", "斬", "참형", "梟首", "효수",
             "轘裂", "환열", "誅", "능지", "처참"],
    "재변": ["日食", "日蝕", "일식", "月食", "월식", "地震", "지진", "地動",
             "彗星", "혜성", "客星", "객성", "星變", "雷震", "벼락"],
    "즉위": ["卽位", "즉위", "禪位", "선위", "內禪", "내선", "受禪"],
    "반정": ["反正", "반정", "謀反", "모반", "靖難", "정난", "廢位", "폐위"],
}


def classify(title: str, body: str = "") -> list[str]:
    """Return the list of event types whose keywords appear in title+body."""
    text = (title or "") + " " + (body or "")
    return [ev for ev, kws in EVENT_LEXICON.items() if any(k in text for k in kws)]
