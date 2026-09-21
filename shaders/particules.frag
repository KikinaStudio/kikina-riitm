#version 330
// Un grain : rond, doux sur les bords (mouvement fluide même très lent).
in float lumiere;
out float sortie;
void main() {
    vec2 c = gl_PointCoord * 2.0 - 1.0;
    sortie = lumiere * exp(-dot(c, c) * 4.0);
}
