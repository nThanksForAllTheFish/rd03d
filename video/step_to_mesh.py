#!/usr/bin/env python3
"""Tessellate a STEP file to triangles with per-face colours (XCAF), saved as .npz.

    uv run --quiet --with cadquery python3 step_to_mesh.py in.step out.npz [lin_tol_mm]

Output arrays: tris (N,3,3) float32 in the STEP's native frame (mm), cols (N,3) uint8.
Faces with no colour in the file get a neutral grey.
"""
import sys
import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv
from OCP.TDF import TDF_LabelSequence
from OCP.Quantity import Quantity_Color
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_REVERSED
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

src, dst = sys.argv[1], sys.argv[2]
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.08

doc = TDocStd_Document(TCollection_ExtendedString("doc"))
rd = STEPCAFControl_Reader()
rd.SetColorMode(True); rd.SetNameMode(True)
if rd.ReadFile(src) != IFSelect_RetDone:
    sys.exit("read failed")
rd.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
labels = TDF_LabelSequence(); st.GetFreeShapes(labels)

def color_of(shape):
    c = Quantity_Color()
    for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv):
        if ct.GetColor(shape, kind, c):
            return (int(c.Red() * 255), int(c.Green() * 255), int(c.Blue() * 255))
    return None

tris, cols = [], []
n_faces = n_col = 0
for i in range(1, labels.Length() + 1):
    shape = st.GetShape_s(labels.Value(i))
    BRepMesh_IncrementalMesh(shape, tol, False, 0.5, True)
    ex_s = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex_s.More():
        solid = ex_s.Current(); sc = color_of(solid)   # per-solid fallback colour
        ex_f = TopExp_Explorer(solid, TopAbs_FACE)
        while ex_f.More():
            face = TopoDS.Face_s(ex_f.Current()); n_faces += 1
            col = color_of(face) or sc
            if col is not None: n_col += 1
            else: col = (150, 150, 150)
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is not None:
                trsf = loc.Transformation()
                nn = tri.NbNodes()
                pts = np.empty((nn, 3))
                for k in range(1, nn + 1):
                    p = tri.Node(k).Transformed(trsf)
                    pts[k - 1] = (p.X(), p.Y(), p.Z())
                rev = face.Orientation() == TopAbs_REVERSED
                for k in range(1, tri.NbTriangles() + 1):
                    a, b, c_ = tri.Triangle(k).Get()
                    t = (pts[a - 1], pts[c_ - 1], pts[b - 1]) if rev else (pts[a - 1], pts[b - 1], pts[c_ - 1])
                    tris.append(t); cols.append(col)
            ex_f.Next()
        ex_s.Next()

tris = np.asarray(tris, np.float32); cols = np.asarray(cols, np.uint8)
np.savez_compressed(dst, tris=tris, cols=cols)
lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
print("%s: %d triangles, %d faces (%d coloured), bbox x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f"
      % (src.split('/')[-1], len(tris), n_faces, n_col, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
uniq = {}
for c in map(tuple, cols): uniq[c] = uniq.get(c, 0) + 1
print("  colours:", sorted(uniq.items(), key=lambda kv: -kv[1])[:8])
