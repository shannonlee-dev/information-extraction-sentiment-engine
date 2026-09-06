"""Local POS grammar. Proximity only bounds an already licensed attachment."""

from __future__ import annotations

import math

from sentiment_engine.models import ModifierLink, MorphToken, SentimentEvent, SentimentMatch

_PREDICATES = {'VA','VV','VX','XSA','XSV','VCP'}
_LINE_BREAKS = frozenset('\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')


def link_modifiers(text: str, tokens: tuple[MorphToken,...], events: tuple[SentimentEvent,...]) -> tuple[ModifierLink,...]:
    from sentiment_engine.sentiment import _get_modifiers
    emphasis = _get_modifiers()['emphasizers']
    links=[]
    consumed=set()
    lexical={i for event in events for i in range(event.token_start,event.token_end)}

    def is_token(i, morph=None, positions=None):
        return 0 <= i < len(tokens) and (morph is None or tokens[i].morph==morph) and (
            positions is None or tokens[i].pos in positions)

    def skip(i, positions):
        while is_token(i,positions=positions):
            i+=1
        return i

    def attach(owner, start, end, kind, rule, multiplier=1.0):
        event=events[owner]
        if start<0 or end>len(tokens) or start>=end or any(i in consumed or i in lexical for i in range(start,end)):
            return False
        lo=min(tokens[start].start,tokens[event.token_start].start)
        hi=max(tokens[end-1].end,tokens[event.token_end-1].end)
        if any(c in _LINE_BREAKS for c in text[lo:hi]):
            return False
        distances=[abs(tokens[i].eojeol_index-tokens[j].eojeol_index)-1
                   for i in (start,end-1) for j in (event.token_start,event.token_end-1)]
        if min(distances)>2:
            return False
        links.append(ModifierLink(owner,start,end,kind,rule,multiplier))
        consumed.update(range(start,end))
        return True

    # Atomic entries own all their internal operators before grammar runs.
    for owner,event in enumerate(events):
        if event.atomic:
            links.append(ModifierLink(owner,event.token_start,event.token_end,'consumed','atomic_lexeme',1.0))
            consumed.update(range(event.token_start,event.token_end))

    for owner,event in enumerate(events):
        end=event.token_end
        last=tokens[end-1]
        predicate=last.pos in _PREDICATES
        nominal=last.pos.startswith(('NN','XR'))
        # Prefix chain is contiguous MAG morphology, never nearest sentiment.
        prefix=[]
        i=event.token_start-1
        while is_token(i,positions={'MAG'}) and i not in lexical:
            token=tokens[i]
            if token.morph in emphasis:
                prefix.append((i,'emphasis',emphasis[token.morph].multiplier))
            elif predicate and token.morph in {'안','못'}:
                prefix.append((i,'negation',1.0))
            else:
                break
            i-=1
        for i,kind,multiplier in reversed(prefix):
            attach(owner,i,i+1,kind,'prefix_adverb' if kind=='negation' else 'predicate_emphasis',multiplier)

        cursor=skip(end,{'EP'}) if predicate else end
        aux_end=None
        if nominal:
            while is_token(cursor) and tokens[cursor].pos.startswith('J'):
                cursor+=1
            if is_token(cursor,'없',{'VA'}) or is_token(cursor,'아니',{'VCN'}):
                if attach(owner,cursor,cursor+1,'negation','nominal_absence'):
                    aux_end=cursor+1
            # 못하다 itself can realize the nominal light-verb negation.
            elif is_token(cursor, '못하', {'VV', 'VX'}):
                attach(owner,cursor,cursor+1,'negation','nominal_light_verb')
            # A nominal light-verb predicate, not a quoted speech complement.
            elif is_token(cursor,positions={'MAG'}) and tokens[cursor].morph in {'안','못'}:
                neg=cursor
                i=cursor+1
                while is_token(i,positions={'MAG'}) and tokens[i].morph in emphasis:
                    i+=1
                if is_token(i,positions={'VV','XSV','VX'}) and tokens[i].morph in {'하','되'}:
                    if attach(owner,neg,neg+1,'negation','nominal_light_verb'):
                        for emph in range(neg+1,i):
                            attach(owner,emph,emph+1,'emphasis','predicate_emphasis',emphasis[tokens[emph].morph].multiplier)

        # Repeated -지 + auxiliary covers both predicate negation and
        # nominal absence + -지는 않다 without creating auxiliary events.
        while predicate or aux_end is not None:
            cursor=skip(aux_end if aux_end is not None else cursor,{'EP'})
            if is_token(cursor,'지',{'EC'}):
                j=skip(cursor+1,{'JX'})
                if (is_token(j,'않',{'VX'}) or is_token(j,'못하',{'VX','VV'})):
                    if attach(owner,j,j+1,'negation','postverbal_ji'):
                        aux_end=j+1
                        predicate=False
                        continue
            break

        # Only the nominalization of this already-negated predicate licenses
        # the outer 아니다. EF/punctuation/another noun stops the chain.
        if aux_end is not None:
            j=skip(aux_end,{'EP'})
            if is_token(j,positions={'ETM'}):
                j+=1
                if is_token(j,'것',{'NNB'}):
                    j+=1
                    j=skip(j,{'JX','JKS'})
                    if is_token(j,'아니',{'VCN'}):
                        attach(owner,j,j+1,'negation','nominalized_double_negation')
    return tuple(links)


def score_events(text: str, tokens: tuple[MorphToken,...], events: tuple[SentimentEvent,...],
                 links: tuple[ModifierLink,...], *, apply_modifiers: bool) -> list[SentimentMatch]:
    matches=[]
    for index,event in enumerate(events):
        owned=[link for link in links if link.event_index==index] if apply_modifiers else []
        negations=sum(link.kind=='negation' for link in owned)
        multiplier=min(2.0,math.prod(link.multiplier for link in owned if link.kind=='emphasis'))
        start=tokens[event.token_start].start
        end=tokens[event.token_end-1].end
        # Public raw retains local endings/particles, while internal event
        # ranges denote only the lexical key. Never absorb another event.
        stop=events[index+1].token_start if index+1<len(events) else len(tokens)
        cursor=event.token_end
        while cursor<stop and tokens[cursor].eojeol_index==tokens[event.token_end-1].eojeol_index:
            suffix=tokens[cursor]
            if suffix.pos.startswith('J') or suffix.pos in {'EP','EF','EC','ETM','ETN','VCP'}:
                end=max(end,suffix.end)
                cursor+=1
            else:
                break
        matches.append(SentimentMatch(event.term,text[start:end],event.score,float(multiplier),negations,
                                      float(event.score*multiplier*(-1)**negations),start,end))
    return matches
