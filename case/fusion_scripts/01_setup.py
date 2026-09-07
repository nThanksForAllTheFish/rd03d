import adsk.core
import adsk.fusion

PARAMS = [
    ("wall", "2 mm", "shell wall thickness"),
    ("windowT", "1.2 mm", "radar window remaining thickness"),
    ("boardClear", "0.25 mm", "clearance around boards"),
    ("usbClear", "0.4 mm", "USB cutout clearance"),
    ("tapeRecess", "0.6 mm", "adhesive tape recess depth"),
    ("backT", "2 mm", "back plate thickness"),
    ("intW", "42 mm", "interior width"),
    ("intH", "46 mm", "interior height"),
    ("intD", "14 mm", "interior depth"),
    ("rimGap", "0.15 mm", "plate-to-shell fit gap per side"),
    ("snapBump", "0.5 mm", "snap bump proudness"),
    ("radarW", "15.1 mm", "RD-03D board width"),
    ("radarH", "44.0 mm", "RD-03D board length"),
    ("radarT", "6.35 mm", "RD-03D thickness incl rear connector"),
    ("radarCx", "-11.5 mm", "radar bay center X"),
    ("xiaoW", "22.5 mm", "XIAO width incl USB overhang"),
    ("xiaoH", "17.8 mm", "XIAO depth"),
    ("xiaoCx", "8.0 mm", "XIAO bay center X"),
    ("postH", "3 mm", "XIAO post height"),
]


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct) if app.activeProduct else None
    if des is None:
        doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        des = adsk.fusion.Design.cast(app.activeProduct)
        print("created new design document:", doc.name)
    elif (des.userParameters.itemByName("wall") is None
          and (des.rootComponent.occurrences.count > 0
               or des.rootComponent.bRepBodies.count > 0)):
        raise RuntimeError("active design has other content and no case "
                           "params - not hijacking it; ask the controller")
    des.designType = adsk.fusion.DesignTypes.ParametricDesignType
    ups = des.userParameters
    for name, expr, comment in PARAMS:
        p = ups.itemByName(name)
        if p is None:
            ups.add(name, adsk.core.ValueInput.createByString(expr), "mm", comment)
            print("added", name, "=", expr)
        else:
            print("exists", name, "=", p.expression)
    print("user params total:", ups.count)
