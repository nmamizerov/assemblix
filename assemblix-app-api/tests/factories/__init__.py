"""Data factories.

The primary entity factories are exposed as pytest fixtures in
``tests/conftest.py`` (``user_factory``, ``auth_user``, ``api_key``) because they
need the transactional test session. Add pure, session-less builders here as the
suite grows (e.g. DTO/request payload builders).
"""
