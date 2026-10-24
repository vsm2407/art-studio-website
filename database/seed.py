
import json
import os
import shutil
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "seedData" / "seed.json"
SOURCE_IMAGES = BASE_DIR / "seedData" / "images"
DEST_IMAGES = BASE_DIR / "static" / "images"

load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "art_studio"),
}


def main():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    connection = mysql.connector.connect(**DB_CONFIG)

    try:
        cursor = connection.cursor()

        # Copy the original painting images.
        DEST_IMAGES.mkdir(parents=True, exist_ok=True)

        for painting in data["paintings"]:
            filename = Path(painting["imageUrl"]).name
            source = SOURCE_IMAGES / filename

            if not source.exists():
                raise FileNotFoundError(f"Image not found: {source}")

            shutil.copy2(source, DEST_IMAGES / filename)

        # Save the mural price supplied by the dataset.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS studio_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_value VARCHAR(255) NOT NULL
            )
        """)

        cursor.execute("""
            INSERT INTO studio_settings (setting_key, setting_value)
            VALUES ('mural_rate_per_sqft', %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
        """, (str(data["mural"]["ratePerSqFt"]),))

        # Import paintings.
        for p in data["paintings"]:
            filename = Path(p["imageUrl"]).name

            cursor.execute("""
                INSERT INTO paintings
                    (painting_code, title, artist, description,
                     price, image_path, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    artist = VALUES(artist),
                    description = VALUES(description),
                    price = VALUES(price),
                    image_path = VALUES(image_path),
                    status = VALUES(status)
            """, (
                p["id"],
                p["title"],
                p["artist"],
                p["description"],
                p["price"],
                "images/" + filename,
                p["status"],
            ))

        # Import pottery items.
        for item in data["potteryItems"]:
            cursor.execute("""
                INSERT INTO pottery_items (item_name)
                VALUES (%s)
                ON DUPLICATE KEY UPDATE item_name = VALUES(item_name)
            """, (item["name"],))

        # Import glaze options.
        for glaze in data["glazes"]:
            cursor.execute("""
                INSERT INTO pottery_glazes (glaze_name)
                VALUES (%s)
                ON DUPLICATE KEY UPDATE glaze_name = VALUES(glaze_name)
            """, (glaze["name"],))

        # Create the studio account using a password hash.
        studio = data["studioAccount"]
        password_hash = generate_password_hash(studio["password"])

        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, 'admin')
            ON DUPLICATE KEY UPDATE
                password_hash = VALUES(password_hash),
                role = 'admin'
        """, (
            "Studio Admin",
            studio["email"],
            password_hash,
        ))

        connection.commit()

        print("Dataset imported successfully!")
        print("Paintings:", len(data["paintings"]))
        print("Pottery items:", len(data["potteryItems"]))
        print("Glazes:", len(data["glazes"]))
        print("Studio account:", studio["email"])
        print("Mural rate:", data["mural"]["ratePerSqFt"])

        cursor.close()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
