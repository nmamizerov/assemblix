"""Direct clients for providers that are not OpenAI-compatible.

LiteLLM fronts everything that speaks the OpenAI API. These two do not — they
have their own REST surfaces and their own voice catalogs — so they get hand-
written clients that the capability seams call into.
"""
