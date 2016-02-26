# -*- coding: utf-8 -*-

import pandas

class NUTS(object):
    """docstring for NUTS"""
    def __init__(self, path):
        super(NUTS, self).__init__()
        self._children = {}
        self._labels = {}
        self._region_objects = {}

        data = pandas.read_excel(path)
        codes = data['NUTS CODE']
        for idx, row in data.iterrows():
            code, label = row['NUTS CODE'], row['NUTS LABEL']
            self._labels[code] = label
            children = set(filter(lambda c: c[:-1] == code, codes))
            if len(children) > 0:
                self._children[code] = children

        self._levels = {l: set(filter(lambda c: len(c) == l + 2, codes)) for l in (0, 1, 2, 3)}

    def descendants(self, code, level):
        code_level = len(code) - 2
        if level <= code_level:
            raise ValueError('cannot get descendants at level {} for {}'.format(level, code))
        if level == code_level + 1:
            return self._children[code]
        else:
            return set.union(*[self.descendants(c, level) for c in self._children[code]])

    def children(self, code):
        return self._children[code]

    def ancestor(self, code, level):
        ancestor_code_len = level + 2
        if ancestor_code_len < 2:
            raise ValueError('cannot get ancestor for {}'.format(code))
        return code[:ancestor_code_len]

    def parent(self, code):
        parent_level = len(code) - 3
        return self.ancestor(code, parent_level)

    def level(self, level):
        return self._levels[level]
