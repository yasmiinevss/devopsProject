#!/usr/bin/env python3
"""
Script d'initialisation de la base de données
Crée la table items si elle n'existe pas
"""
import os
import sys

import psycopg2
from psycopg2 import sql

# Variables d'environnement
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "tpkubernetes")


def init_database():
    """Initialiser la base de données et créer la table items"""
    print("🔌 Connexion à la base de données...")
    print(f"   Host: {DB_HOST}:{DB_PORT}")
    print(f"   Database: {DB_NAME}")
    print(f"   User: {DB_USER}")
    
    try:
        # Connexion à PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("✅ Connexion réussie")
        
        # Créer la table
        cur = conn.cursor()
        
        print("\n📋 Création de la table 'items'...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        conn.commit()
        
        # Vérifier que la table existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'items'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if table_exists:
            print("✅ Table 'items' créée/vérifiée avec succès")
            
            # Afficher la structure de la table
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'items'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            
            print("\n📊 Structure de la table 'items':")
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"   - {col[0]}: {col[1]} ({nullable})")
            
            # Compter les items existants
            cur.execute("SELECT COUNT(*) FROM items")
            count = cur.fetchone()[0]
            print(f"\n📦 Nombre d'items dans la table: {count}")
        else:
            print("❌ Erreur: La table n'a pas pu être créée")
            sys.exit(1)
        
        cur.close()
        conn.close()
        
        print("\n🎉 Initialisation de la base de données terminée avec succès!")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Erreur de connexion à la base de données:")
        print(f"   {e}")
        print("\n💡 Vérifiez que:")
        print("   - PostgreSQL est démarré")
        print("   - Les variables d'environnement sont correctes")
        print("   - La base de données existe")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur lors de l'initialisation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  Initialisation de la base de données")
    print("=" * 60)
    print()
    
    init_database()

