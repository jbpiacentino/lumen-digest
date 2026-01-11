# lumen-digest
A news digest experiment


# Migrations
## Ex: Updating the Article schema
- Modify models.py to add or remove fields
- ```docker-compose exec backend alembic revision --autogenerate -m "migration description"```
- Review the generated migration in /backend/migrations/versions/xxxx_migration_description
- apply migration : ```docker-compose exec backend alembic upgrade head```

