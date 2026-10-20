"""AI Pre-Mortems: can frontier models predict how code and systems fail?

CS3263 project (Group 19). Two scales of failure finding:
  sp1 - one function: CSP/SMT search for an input that violates the spec (Z3).
  sp2 - one design: STRIPS planning for an event trace that reaches a violation
        (SATPlan for shortest traces, FF-style forward search to certify fixes).
"""
