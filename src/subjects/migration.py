"""Migration script for NeuroForge subject system.

Migrates from the old single-collection structure to the new
per-subject organization. This is a one-time migration that:

1. Creates the "General" default subject
2. Moves existing data files to the General subject directory
3. Migrates ChromaDB collections to subject-scoped collections
4. Creates a migration marker to prevent re-running

Usage:
    python -m src.subjects.migration

Or programmatically:
    from src.subjects.migration import migrate_to_subjects
    migrate_to_subjects()
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("neuroforge.migration")

# Paths
OLD_KNOWLEDGE_GRAPH = Path("./knowledge_graph.json")
OLD_LEARNING_STATE = Path("./learning_state.json")
OLD_SR_STATE = Path("./sr_state.json")
OLD_CHROMA_DB = Path("./chroma_db")

DATA_DIR = Path("./data")
MIGRATION_MARKER = DATA_DIR / ".migration_complete"
BACKUP_DIR = DATA_DIR / "pre_migration_backup"


def needs_migration() -> bool:
    """Check if migration is needed.
    
    Returns True if:
    - Old-style data files exist at root level
    - Migration marker doesn't exist
    """
    if MIGRATION_MARKER.exists():
        return False
    
    old_files_exist = any([
        OLD_KNOWLEDGE_GRAPH.exists(),
        OLD_LEARNING_STATE.exists(),
        OLD_SR_STATE.exists(),
    ])
    
    return old_files_exist


def get_migration_info() -> dict:
    """Get information about what needs to be migrated.
    
    Returns:
        Dictionary with migration status and files to migrate.
    """
    return {
        "needs_migration": needs_migration(),
        "migration_complete": MIGRATION_MARKER.exists(),
        "files_to_migrate": {
            "knowledge_graph": OLD_KNOWLEDGE_GRAPH.exists(),
            "learning_state": OLD_LEARNING_STATE.exists(),
            "sr_state": OLD_SR_STATE.exists(),
            "chroma_db": OLD_CHROMA_DB.exists(),
        },
        "backup_exists": BACKUP_DIR.exists(),
    }


def create_backup() -> bool:
    """Create backup of existing data before migration.
    
    Returns:
        True if backup was created successfully.
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # Backup JSON files
        for src_file in [OLD_KNOWLEDGE_GRAPH, OLD_LEARNING_STATE, OLD_SR_STATE]:
            if src_file.exists():
                dest_file = BACKUP_DIR / src_file.name
                shutil.copy2(src_file, dest_file)
                logger.info(f"Backed up {src_file} to {dest_file}")
        
        # Note: We don't backup ChromaDB as it can be large and we're
        # migrating the collections, not deleting them
        
        # Write backup metadata
        metadata = {
            "backup_time": datetime.utcnow().isoformat(),
            "files_backed_up": [
                str(f) for f in [OLD_KNOWLEDGE_GRAPH, OLD_LEARNING_STATE, OLD_SR_STATE]
                if f.exists()
            ],
        }
        metadata_file = BACKUP_DIR / "backup_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        return True
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return False


def migrate_json_files(subject_id: str = "general") -> dict:
    """Migrate JSON data files to subject directory.
    
    Args:
        subject_id: Target subject ID (default "general").
        
    Returns:
        Dictionary with migration results for each file.
    """
    from .storage import SubjectStorage
    
    storage = SubjectStorage(str(DATA_DIR))
    storage.initialize_subject_files(subject_id)
    
    results = {}
    
    # Migrate knowledge_graph.json
    if OLD_KNOWLEDGE_GRAPH.exists():
        try:
            dest = storage.get_knowledge_graph_path(subject_id)
            shutil.copy2(OLD_KNOWLEDGE_GRAPH, dest)
            results["knowledge_graph"] = {"status": "success", "source": str(OLD_KNOWLEDGE_GRAPH), "dest": str(dest)}
            logger.info(f"Migrated knowledge_graph.json to {dest}")
        except Exception as e:
            results["knowledge_graph"] = {"status": "error", "error": str(e)}
            logger.error(f"Failed to migrate knowledge_graph.json: {e}")
    
    # Migrate learning_state.json
    if OLD_LEARNING_STATE.exists():
        try:
            dest = storage.get_learning_state_path(subject_id)
            shutil.copy2(OLD_LEARNING_STATE, dest)
            results["learning_state"] = {"status": "success", "source": str(OLD_LEARNING_STATE), "dest": str(dest)}
            logger.info(f"Migrated learning_state.json to {dest}")
        except Exception as e:
            results["learning_state"] = {"status": "error", "error": str(e)}
            logger.error(f"Failed to migrate learning_state.json: {e}")
    
    # Migrate sr_state.json
    if OLD_SR_STATE.exists():
        try:
            dest = storage.get_sr_state_path(subject_id)
            shutil.copy2(OLD_SR_STATE, dest)
            results["sr_state"] = {"status": "success", "source": str(OLD_SR_STATE), "dest": str(dest)}
            logger.info(f"Migrated sr_state.json to {dest}")
        except Exception as e:
            results["sr_state"] = {"status": "error", "error": str(e)}
            logger.error(f"Failed to migrate sr_state.json: {e}")
    
    return results


def migrate_chroma_collections(subject_id: str = "general") -> dict:
    """Migrate ChromaDB collections to subject-scoped collections.
    
    This copies data from the old global collections to new subject-scoped
    collections. The old collections are preserved (not deleted).
    
    Args:
        subject_id: Target subject ID (default "general").
        
    Returns:
        Dictionary with migration results.
    """
    results = {"chunks": None, "concepts": None}
    
    if not OLD_CHROMA_DB.exists():
        return results
    
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        
        # Connect to the old ChromaDB
        client = chromadb.PersistentClient(path=str(OLD_CHROMA_DB))
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        
        # Get collection names
        old_chunks_name = "neuroforge_chunks"
        old_concepts_name = "neuroforge_concepts"
        new_chunks_name = f"subject_{subject_id}_chunks"
        new_concepts_name = f"subject_{subject_id}_concepts"
        
        # Check if old collections exist
        existing_collections = [c.name for c in client.list_collections()]
        
        # Migrate chunks collection
        if old_chunks_name in existing_collections:
            try:
                old_chunks = client.get_collection(old_chunks_name, embedding_function=embedding_fn)
                
                # Get all data from old collection
                old_data = old_chunks.get(include=["documents", "metadatas", "embeddings"])
                
                if old_data["ids"]:
                    # Create new collection
                    new_chunks = client.get_or_create_collection(
                        name=new_chunks_name,
                        embedding_function=embedding_fn,
                    )
                    
                    # Add subject_id to metadata
                    updated_metadatas = []
                    for meta in old_data["metadatas"]:
                        if meta is None:
                            meta = {}
                        meta["subject_id"] = subject_id
                        updated_metadatas.append(meta)
                    
                    # Add to new collection
                    new_chunks.add(
                        ids=old_data["ids"],
                        documents=old_data["documents"],
                        metadatas=updated_metadatas,
                        embeddings=old_data["embeddings"],
                    )
                    
                    results["chunks"] = {
                        "status": "success",
                        "count": len(old_data["ids"]),
                        "source": old_chunks_name,
                        "dest": new_chunks_name,
                    }
                    logger.info(f"Migrated {len(old_data['ids'])} chunks to {new_chunks_name}")
                else:
                    results["chunks"] = {"status": "empty", "message": "No chunks to migrate"}
                    
            except Exception as e:
                results["chunks"] = {"status": "error", "error": str(e)}
                logger.error(f"Failed to migrate chunks collection: {e}")
        
        # Migrate concepts collection
        if old_concepts_name in existing_collections:
            try:
                old_concepts = client.get_collection(old_concepts_name, embedding_function=embedding_fn)
                
                # Get all data from old collection
                old_data = old_concepts.get(include=["documents", "metadatas", "embeddings"])
                
                if old_data["ids"]:
                    # Create new collection
                    new_concepts = client.get_or_create_collection(
                        name=new_concepts_name,
                        embedding_function=embedding_fn,
                    )
                    
                    # Add subject_id to metadata
                    updated_metadatas = []
                    for meta in old_data["metadatas"]:
                        if meta is None:
                            meta = {}
                        meta["subject_id"] = subject_id
                        updated_metadatas.append(meta)
                    
                    # Add to new collection
                    new_concepts.add(
                        ids=old_data["ids"],
                        documents=old_data["documents"],
                        metadatas=updated_metadatas,
                        embeddings=old_data["embeddings"],
                    )
                    
                    results["concepts"] = {
                        "status": "success",
                        "count": len(old_data["ids"]),
                        "source": old_concepts_name,
                        "dest": new_concepts_name,
                    }
                    logger.info(f"Migrated {len(old_data['ids'])} concepts to {new_concepts_name}")
                else:
                    results["concepts"] = {"status": "empty", "message": "No concepts to migrate"}
                    
            except Exception as e:
                results["concepts"] = {"status": "error", "error": str(e)}
                logger.error(f"Failed to migrate concepts collection: {e}")
        
    except ImportError:
        results["error"] = "ChromaDB not installed"
    except Exception as e:
        results["error"] = str(e)
        logger.error(f"Failed to migrate ChromaDB collections: {e}")
    
    return results


def mark_migration_complete() -> None:
    """Write migration completion marker."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "migration_time": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }
    MIGRATION_MARKER.write_text(json.dumps(marker_data, indent=2))
    logger.info(f"Migration complete marker written to {MIGRATION_MARKER}")


def migrate_to_subjects(
    subject_id: str = "general",
    create_backup: bool = True,
    force: bool = False,
) -> dict:
    """Run the complete migration to subject-based organization.
    
    Args:
        subject_id: Subject ID to migrate data to (default "general").
        create_backup: Whether to backup existing files first.
        force: Force migration even if marker exists.
        
    Returns:
        Dictionary with complete migration results.
    """
    results = {
        "status": "pending",
        "backup": None,
        "json_files": None,
        "chroma": None,
        "errors": [],
    }
    
    # Check if migration needed
    if not force and not needs_migration():
        if MIGRATION_MARKER.exists():
            results["status"] = "already_complete"
            results["message"] = "Migration was already completed"
            return results
        else:
            results["status"] = "not_needed"
            results["message"] = "No old data files found to migrate"
            return results
    
    logger.info("Starting migration to subject-based organization...")
    
    # Step 1: Create backup
    if create_backup:
        backup_success = globals()["create_backup"]()  # Call the function, not bool param
        results["backup"] = {"status": "success" if backup_success else "failed"}
        if not backup_success:
            results["errors"].append("Backup creation failed")
    
    # Step 2: Migrate JSON files
    results["json_files"] = migrate_json_files(subject_id)
    
    # Step 3: Migrate ChromaDB collections
    results["chroma"] = migrate_chroma_collections(subject_id)
    
    # Step 4: Mark complete
    mark_migration_complete()
    
    # Determine overall status
    has_errors = bool(results["errors"])
    json_errors = any(
        r.get("status") == "error" 
        for r in (results["json_files"] or {}).values() 
        if isinstance(r, dict)
    )
    chroma_errors = results["chroma"].get("error") is not None if results["chroma"] else False
    
    if has_errors or json_errors or chroma_errors:
        results["status"] = "completed_with_errors"
    else:
        results["status"] = "success"
    
    logger.info(f"Migration completed with status: {results['status']}")
    return results


def cleanup_old_files(dry_run: bool = True) -> dict:
    """Remove old data files after confirming migration success.
    
    WARNING: This permanently deletes the old files. Only run after
    verifying the migration was successful.
    
    Args:
        dry_run: If True, only report what would be deleted.
        
    Returns:
        Dictionary with cleanup results.
    """
    results = {"dry_run": dry_run, "files": []}
    
    if not MIGRATION_MARKER.exists():
        results["error"] = "Migration not complete. Run migration first."
        return results
    
    old_files = [OLD_KNOWLEDGE_GRAPH, OLD_LEARNING_STATE, OLD_SR_STATE]
    
    for old_file in old_files:
        if old_file.exists():
            if dry_run:
                results["files"].append({"path": str(old_file), "action": "would_delete"})
            else:
                try:
                    old_file.unlink()
                    results["files"].append({"path": str(old_file), "action": "deleted"})
                    logger.info(f"Deleted {old_file}")
                except Exception as e:
                    results["files"].append({"path": str(old_file), "action": "error", "error": str(e)})
    
    return results


# CLI entry point
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    
    print("NeuroForge Subject Migration Tool")
    print("=" * 40)
    
    info = get_migration_info()
    print(f"\nMigration status:")
    print(f"  Needs migration: {info['needs_migration']}")
    print(f"  Already complete: {info['migration_complete']}")
    print(f"\nFiles to migrate:")
    for name, exists in info["files_to_migrate"].items():
        status = "✓ exists" if exists else "✗ not found"
        print(f"  {name}: {status}")
    
    if not info["needs_migration"]:
        if info["migration_complete"]:
            print("\n✓ Migration was already completed.")
        else:
            print("\n✓ No migration needed (no old files found).")
        sys.exit(0)
    
    print("\nStarting migration...")
    results = migrate_to_subjects()
    
    print(f"\nMigration completed with status: {results['status']}")
    if results["errors"]:
        print(f"Errors: {results['errors']}")
    
    sys.exit(0 if results["status"] == "success" else 1)
