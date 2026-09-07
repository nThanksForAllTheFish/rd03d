import adsk.core
import adsk.fusion

OUT = "/path/to/rd03d/case"


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    em = des.exportManager
    for comp_name, fname in (("BackPlate", "rd03d_case_back.stl"),
                             ("FrontShell", "rd03d_case_shell.stl")):
        occ = None
        for o in root.occurrences:
            if o.component.name == comp_name:
                occ = o
        if occ is None:
            raise RuntimeError("missing component " + comp_name)
        opts = em.createSTLExportOptions(occ, f"{OUT}/{fname}")
        opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        em.execute(opts)
        print("exported", fname)
