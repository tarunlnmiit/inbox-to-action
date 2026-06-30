"""Tool implementations for inbox-to-action.

Each LLM-dependent tool takes an injected `reasoner` (see reasoner.py) so the
same code runs under a real provider or under Claude Code (host mode). IO tools
(gmail) take no reasoner.
"""
