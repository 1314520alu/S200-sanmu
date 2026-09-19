// S200 front beam face holes (mm)
// Origin: plate center. +X right, +Y up.
// Measured from drawing: 310×94 plate, 110×69 for 4×Ø3, plus two bottom M3.
plate_l = 310;
plate_h = 94;
hole_d = 3;

// 4×Ø3 (110 × 69)
cad_4x = [
  [-55,  34.5], [55,  34.5],
  [-55, -34.5], [55, -34.5]
];

// Two extra M3 on bottom row only (inside 110 span) — measured ≈±30.15, rounded to ±30
extra_bottom_m3 = [
  [-30, -34.5], [30, -34.5]
];

module plate() {
  translate([0,0,-2]) linear_extrude(2) offset(r=2) square([plate_l, plate_h], center=true);
}
module holes(list) {
  for (p = list) translate([p[0], p[1], -3]) cylinder(h=6, d=hole_d, $fn=48);
}

difference() {
  plate();
  holes(cad_4x);
  holes(extra_bottom_m3);
}
