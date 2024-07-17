Types
#####

Main types
==========

.. we need to exclude QueryAnalysis because autodoc pydantic doesn't support it, we add it below
.. automodule:: app._types
   :members:
   :exclude-members: QueryAnalysis

.. autopydantic_model:: app._types.QueryAnalysis
   :model-show-json: False

.. autoclass:: app._types.QueryAnalysis
    :members:
    :no-index:

Validations
===========

.. automodule:: app.validations
   :members:
