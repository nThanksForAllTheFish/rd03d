import adsk.core
import adsk.fusion

OUT = "/path/to/rd03d/case"


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    em = des.exportManager
    for comp_name, fname in (("BackPlate", "rd03d_case_back.stl"),
                             ("FrontShell", "rd03d_case_shell.stl"),
                             ("PirPlug", "rd03d_pir_plug.stl")):
        occ = None
        for o in root.occurrences:
            # prefix match: a rebuilt component can carry a "(1)" suffix
            # until the doc is saved (deleted components reserve their
            # names in the document's name registry)
            if o.component.name.startswith(comp_name):
                occ = o
        if occ is None:
            raise RuntimeError("missing component " + comp_name)
        # export the COMPONENT, not the occurrence: the plug's occurrence is
        # parked tilted in the pod's bore for the picture and the fit check,
        # and the STL must come out flat in its own frame (z 0..pirPlugL).
        # BackPlate and FrontShell sit at identity, so nothing changes for them.
        opts = em.createSTLExportOptions(occ.component, f"{OUT}/{fname}")
        opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        em.execute(opts)
        print("exported", fname)
