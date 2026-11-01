import adsk.core
import adsk.fusion

OUT = "/path/to/rd03d/case"  # run_fusion.py fills in the checkout root


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    em = des.exportManager
    for comp_name, fname in (("BackPlate", "rd03d_case_back.stl"),
                             ("FrontShell", "rd03d_case_shell.stl"),
                             ("PirBezel", "rd03d_pir_bezel.stl")):
        occ = None
        for o in root.occurrences:
            # prefix match: a rebuilt component can carry a "(1)" suffix
            # until the doc is saved (deleted components reserve their
            # names in the document's name registry)
            if o.component.name.startswith(comp_name):
                occ = o
        if occ is None:
            raise RuntimeError("missing component " + comp_name)
        # export the COMPONENT, not the occurrence: the bezel's occurrence is
        # parked on the shell's face, turned to its rest angle, for the
        # picture and the fit check, and the STL must come out in its own
        # frame (flange underside on z 0, axis +Z). BackPlate and FrontShell
        # sit at identity, so nothing changes for them. (The 9c plug's STL,
        # rd03d_pir_plug.stl, is gone with the plug.)
        opts = em.createSTLExportOptions(occ.component, f"{OUT}/{fname}")
        opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        em.execute(opts)
        print("exported", fname)
