Installation & Running
======================

Local Installation
------------------

1. Create venv  
2. Install requirements  
3. Run users service  
4. Run rooms service  

Docker Deployment
-----------------

Run both microservices:

.. code-block:: bash

    docker-compose up --build

Running Tests
-------------

.. code-block:: bash

    pytest -v --cov

