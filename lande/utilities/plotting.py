
def plot_ds9_contour(ax,contour,**kwargs):
    """ Parse a ds9 format contour file. Kwargs goes into the plot function. """
    lines=open(os.path.expandvars(contour)).readlines()
    ras,decs=[],[]
    for line in lines:
        if line.strip() is '':
            ax['fk5'].plot(ras,decs,'-',**kwargs)
            ras,decs=[],[]
        else:
            ra,dec=line.split()
            ras.append(float(ra)); decs.append(float(dec))

def fix_axesgrid(grid):
    """ Remove the ticks which overlap with nearby axes. """
    if grid._direction != 'row': 
        raise Exception("Not implemented")

    nrows,ncols=grid._nrows,grid._ncols

    for row in range(nrows):
        for col in range(ncols):
            ax = grid[row*ncols + col]
            if row != 0 and col==0:
                ax.set_yticks(ax.get_yticks()[0:-1])
            if col != ncols-1 and row==nrows-1:
                ax.set_xticks(ax.get_xticks()[0:-1])


def label_axesgrid(grid, stroke=True, **kwargs):
    """ Add "(a)" to first plot, "(b)" to second, ... """

    text_kwargs=dict(frameon=False, loc=2, prop=dict(size=14))
    text_kwargs.update(kwargs)

    for i,g in enumerate(grid):
        _at = AnchoredText('(%s)' % chr(i+97), **text_kwargs)

        if stroke:
            _at.txt._text.set_path_effects([withStroke(foreground="w", linewidth=3)])

        g.add_artist(_at)
