from app.models import Project


project = Project(
    project_uuid="test-123",
    name="Test Water Project",
    location="Ogun State",
    progress=25
)


print("Project created successfully.")
print()
print(project)