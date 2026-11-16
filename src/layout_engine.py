"""Deterministic, collision-conscious relationship diagram auto-layout.

This is deliberately framework independent so it can be tested without Qt.
The highest-degree table in each connected component is placed centrally.
"""
from __future__ import annotations
from collections import deque
from math import cos, sin, pi, ceil


def auto_layout(table_names, relationships, *, horizontal_gap=340, vertical_gap=320):
    """Return integer scene positions for every table without overlapping cards.

    All edges count once, including self-edges (which do not change ranking).
    Separate components are placed in separate horizontal regions.
    """
    names = sorted(set(table_names), key=str.casefold)
    adj = {name:set() for name in names}
    for link in relationships:
        a,b=link.get('parent'),link.get('child')
        if a in adj and b in adj and a != b:
            adj[a].add(b);adj[b].add(a)
    components=[];remaining=set(names)
    while remaining:
        seed=min(remaining,key=str.casefold)
        q=deque([seed]);remaining.remove(seed);part=[]
        while q:
            node=q.popleft();part.append(node)
            for child in sorted(adj[node],key=str.casefold):
                if child in remaining:
                    remaining.remove(child);q.append(child)
        components.append(part)
    components.sort(key=lambda part:(-len(part),-max((len(adj[n]) for n in part),default=0),min(part).casefold()))
    result={}; offset_x=0
    for part in components:
        root=sorted(part,key=lambda n:(-len(adj[n]),n.casefold()))[0]
        distance={root:0};q=deque([root])
        while q:
            current=q.popleft()
            for child in sorted(adj[current],key=lambda n:(-len(adj[n]),n.casefold())):
                if child not in distance:
                    distance[child]=distance[current]+1;q.append(child)
        levels={}
        for name,level in distance.items():levels.setdefault(level,[]).append(name)
        component={root:(0,0)}
        prior_radius=0
        for level in sorted(levels):
            if level==0:continue
            group=sorted(levels[level],key=lambda n:(-len(adj[n]),n.casefold()))
            count=len(group)
            # Uniform radial spacing protects the minimum 254x... card footprint.
            radius=max(prior_radius + max(horizontal_gap,vertical_gap,620),count*185)
            start=-pi/2
            for i,name in enumerate(group):
                angle=start+(2*pi*i/count)
                component[name]=(round(radius*cos(angle)),round(radius*sin(angle)))
            prior_radius=radius
        xs=[x for x,y in component.values()]
        shifted={name:(x-min(xs)+offset_x,y) for name,(x,y) in component.items()}
        result.update(shifted)
        offset_x=max(x for x,y in shifted.values())+horizontal_gap+440
    return result
