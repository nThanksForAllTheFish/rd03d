import adsk.core


def run(_context: str):
    app = adsk.core.Application.get()
    print("Fusion", app.version)
    doc = app.activeDocument
    print("active doc:", doc.name if doc else None)
    print("open docs:", app.documents.count)
