import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os

print('Working dir:', os.getcwd())
print('PNG exists:', os.path.exists('bloque2_modelo_diagram.png'))

img = mpimg.imread('bloque2_modelo_diagram.png')
fig, ax = plt.subplots(figsize=(18, 13))
ax.imshow(img)
ax.axis('off')
plt.tight_layout(pad=0)
plt.savefig('bloque2_modelo.pdf', format='pdf', dpi=200, bbox_inches='tight')
print('PDF guardado: bloque2_modelo.pdf')
print('PDF size:', os.path.getsize('bloque2_modelo.pdf'))
