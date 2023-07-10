from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from fastapi import FastAPI, HTTPException
from selenium.webdriver.support.wait import WebDriverWait
from sqlalchemy import Column, Integer, String, create_engine, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from databases import Database
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import os
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

app = FastAPI()
database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/words_db")
engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
database = Database(database_url)
Base = declarative_base()
EXPAND_BUTTON_XPATH = \
    '//*[@id="yDmH0d"]/c-wiz/div/div[2]/c-wiz/div[2]/c-wiz/div[2]/c-wiz/div/div/div[2]/div[1]/div[2]/div[1]'


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, unique=True)
    definitions = relationship("Definition", backref="word", cascade="all, delete")
    synonyms = relationship("Synonym", backref="word", cascade="all, delete")
    translations = relationship("Translation", backref="word", cascade="all, delete")
    examples = relationship("Example", backref="word", cascade="all, delete")


class Definition(Base):
    __tablename__ = "definitions"

    id = Column(Integer, primary_key=True, index=True)
    word_id = Column(Integer, ForeignKey("words.id"))
    definition = Column(String)


class Synonym(Base):
    __tablename__ = "synonyms"

    id = Column(Integer, primary_key=True, index=True)
    word_id = Column(Integer, ForeignKey("words.id"))
    synonym = Column(String)


class Translation(Base):
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    word_id = Column(Integer, ForeignKey("words.id"))
    translation = Column(String)


class Example(Base):
    __tablename__ = "examples"

    id = Column(Integer, primary_key=True, index=True)
    word_id = Column(Integer, ForeignKey("words.id"))
    example = Column(String)


Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


def fetch_word_data(word: str) -> [list[str], list[str], list[str], list[str]]:
    options = Options()
    options.add_argument("--headless")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(
        service=ChromiumService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()),
        options=options
    )
    try:
        driver.get(f"https://translate.google.com/?sl=en&tl=ru&text={word}&op=translate")
        try:
            expand_button = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, EXPAND_BUTTON_XPATH)))
            expand_button.click()
        except TimeoutException:
            pass

        definition_element = driver.find_elements(By.CLASS_NAME, 'fw3eif')
        definitions = [value.text for value in definition_element if value.text != ""]

        synonyms_elements = driver.find_elements(By.CLASS_NAME, 'MtFg0')
        synonyms = [value.text for value in synonyms_elements if value.text != ""]
        # removing duplicates
        synonyms = list(set(synonyms))

        main_translation_element = driver.find_elements(By.CLASS_NAME, 'HwtZe')
        translations = [value.text for value in main_translation_element if value.text != ""]

        translation_elements = driver.find_elements(By.CLASS_NAME, 'kgnlhe')
        other_translations = [value.text for value in translation_elements if value.text != ""]
        translations.extend(other_translations)

        examples_elements = driver.find_elements(By.CLASS_NAME, 'AZPoqf.OvhKBb')
        examples = [value.text for value in examples_elements if value.text != ""]
        return definitions, synonyms, translations, examples
    finally:
        driver.quit()


@app.get("/word/{word}")
async def get_word(
    word: str,
    include_definitions: bool = False,
    include_synonyms: bool = False,
    include_translations: bool = False,
) -> dict[str, list[str]]:
    db = SessionLocal()
    stored_word = db.query(Word).filter(Word.word == word).first()
    if not stored_word:
        definitions, synonyms, translations, examples = fetch_word_data(word)

        new_word = Word(word=word)
        db.add(new_word)
        db.commit()

        for definition in definitions:
            new_definition = Definition(definition=definition, word_id=new_word.id)
            db.add(new_definition)
        for synonym in synonyms:
            new_synonym = Synonym(synonym=synonym, word_id=new_word.id)
            db.add(new_synonym)
        for translation in translations:
            new_translation = Translation(translation=translation, word_id=new_word.id)
            db.add(new_translation)
        for example in examples:
            new_example = Example(example=example, word_id=new_word.id)
            db.add(new_example)

        db.commit()
        stored_word = db.query(Word).filter(Word.word == word).first()

    return {
        "word": stored_word.word,
        "definition": stored_word.definitions if include_definitions else None,
        "synonyms": stored_word.synonyms if include_synonyms else None,
        "translations": stored_word.translations if include_translations else None,
        "examples": stored_word.examples,
    }


@app.get("/words")
async def get_words(
    page: int = 1,
    limit: int = 10,
    sort_by: str = "word",
    filter: str = "",
    include_definitions: bool = False,
    include_synonyms: bool = False,
    include_translations: bool = False,
) -> dict[str, list[dict[str, str]]]:
    db = SessionLocal()
    query = db.query(Word)
    if filter:
        query = query.filter(Word.word.ilike(f"%{filter}%"))
    total_count = query.count()
    words = query.order_by(sort_by).offset((page - 1) * limit).limit(limit).all()
    result = []
    for word in words:
        response = {
            "word": word.word,
        }
        if include_definitions:
            response["definition"] = word.definition
        if include_synonyms:
            response["synonyms"] = word.synonyms
        if include_translations:
            response["translations"] = word.translations
        result.append(response)
    return {
        "page": page,
        "limit": limit,
        "total_count": total_count,
        "words": result,
    }


@app.delete("/word/{word}")
async def delete_word(word: str) -> dict[str, str]:
    db = SessionLocal()
    deleted_word = db.query(Word).filter(Word.word == word).first()
    if deleted_word:
        db.delete(deleted_word)
        db.commit()
        return {"message": "Word deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Word not found")
