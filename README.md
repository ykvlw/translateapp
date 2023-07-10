## Google Translate APP

The goal of this app is to create a microservice providing an API to work with word definitions/translations taken from Google Translate.

### How to run
    $ docker-compose build
    $ docker-compose up

### How to use
There are three endpoints available:
- word/{word} - to get a word definition
- words/ - to get a list of words
- word/{word} - to delete a word from the db

Simply do a request on the in Postman:    

    GET http://0.0.0.0:8000/word/{word}

Also, there are parameters you can pass:
- include_definitions - to include definitions in the response
- include_synonyms - to include synonyms in the response
- include_translations - to include translations in the response

Example:
    
    GET http://0.0.0.0:8000/word/friendship?include_definitions=True&include_synonyms=True&include_translations=True

Also, you can filter by value when you do a search in list of words:

        GET http://0.0.0.0:8000/words?filter=chal