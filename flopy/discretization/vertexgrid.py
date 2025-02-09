import numpy as np
try:
    from matplotlib.path import Path
except ImportError:
    Path = None

from .grid import Grid, CachedData
from ..utils.geometry import is_clockwise


class VertexGrid(Grid):
    """
    class for a vertex model grid

    Parameters
    ----------
    vertices
        list of vertices that make up the grid
    cell2d
        list of cells and their vertices

    Properties
    ----------
    vertices
        returns list of vertices that make up the grid
    cell2d
        returns list of cells and their vertices

    Methods
    ----------
    get_cell_vertices(cellid)
        returns vertices for a single cell at cellid.
    """

    def __init__(self, vertices=None, cell2d=None, top=None, botm=None, idomain=None,
                 lenuni=None, epsg=None, proj4=None, prj=None, xoff=0.0,
                 yoff=0.0, angrot=0.0, grid_type='vertex',
                 nlay=None, ncpl=None):
        super(VertexGrid, self).__init__(grid_type, top, botm, idomain, lenuni,
                                         epsg, proj4, prj, xoff, yoff, angrot)
        self._vertices = vertices
        self._cell2d = cell2d
        self._top = top
        self._botm = botm
        self._idomain = idomain
        if botm is None:
            self._nlay = nlay
            self._ncpl = ncpl
        else:
            self._nlay = None
            self._ncpl = None

    @property
    def is_valid(self):
        if self._vertices is not None and self._cell2d is not None:
            return True
        return False

    @property
    def is_complete(self):
        if self._vertices is not None and self._cell2d is not None and \
                super(VertexGrid, self).is_complete:
            return True
        return False

    @property
    def nlay(self):
        if self._botm is not None:
            return len(self._botm)
        else:
            return self._nlay

    @property
    def ncpl(self):
        if self._botm is not None:
            return len(self._botm[0])
        else:
            return self._ncpl

    @property
    def shape(self):
        return self.nlay, self.ncpl

    @property
    def extent(self):
        self._copy_cache = False
        xvertices = np.hstack(self.xvertices)
        yvertices = np.hstack(self.yvertices)
        self._copy_cache = True
        return (np.min(xvertices),
                np.max(xvertices),
                np.min(yvertices),
                np.max(yvertices))

    @property
    def grid_lines(self):
        """
        Creates a series of grid line vertices for drawing
        a model grid line collection

        Returns:
            list: grid line vertices
        """
        self._copy_cache = False
        xgrid = self.xvertices
        ygrid = self.yvertices

        lines = []
        for ncell, verts in enumerate(xgrid):
            for ix, vert in enumerate(verts):
                lines.append([(xgrid[ncell][ix - 1], ygrid[ncell][ix - 1]),
                              (xgrid[ncell][ix], ygrid[ncell][ix])])
        self._copy_cache = True
        return lines

    @property
    def xyzcellcenters(self):
        """
        Internal method to get cell centers and set to grid
        """
        cache_index = 'cellcenters'
        if cache_index not in self._cache_dict or \
                self._cache_dict[cache_index].out_of_date:
            self._build_grid_geometry_info()
        if self._copy_cache:
            return self._cache_dict[cache_index].data
        else:
            return self._cache_dict[cache_index].data_nocopy

    @property
    def xyzvertices(self):
        """
        Internal method to get model grid verticies

        Returns:
            list of dimension ncpl by nvertices
        """
        cache_index = 'xyzgrid'
        if cache_index not in self._cache_dict or \
                self._cache_dict[cache_index].out_of_date:
            self._build_grid_geometry_info()
        if self._copy_cache:
            return self._cache_dict[cache_index].data
        else:
            return self._cache_dict[cache_index].data_nocopy

    def intersect(self, x, y, local=False, forgive=False):
        """
        Get the CELL2D number of a point with coordinates x and y
        
        When the point is on the edge of two cells, the cell with the lowest
        CELL2D number is returned.
        
        Parameters
        ----------
        x : float
            The x-coordinate of the requested point
        y : float
            The y-coordinate of the requested point
        local: bool (optional)
            If True, x and y are in local coordinates (defaults to False)
        forgive: bool (optional)
            Forgive x,y arguments that fall outside the model grid and
            return NaNs instead (defaults to False - will throw exception)
    
        Returns
        -------
        icell2d : int
            The CELL2D number
        
        """
        if Path is None:
            s = 'Could not import matplotlib.  Must install matplotlib ' + \
                ' in order to use VertexGrid.intersect() method'
            raise ImportError(s)

        if local:
            # transform x and y to real-world coordinates
            x, y = super(VertexGrid, self).get_coords(x,y)
        xv, yv, zv = self.xyzvertices
        for icell2d in range(self.ncpl):
            xa = np.array(xv[icell2d])
            ya = np.array(yv[icell2d])
            # x and y at least have to be within the bounding box of the cell
            if np.any(x <= xa) and np.any(x >= xa) and \
                    np.any(y <= ya) and np.any(y >= ya):
                path = Path(np.stack((xa, ya)).transpose())
                # use a small radius, so that the edge of the cell is included
                if is_clockwise(xa, ya):
                    radius = -1e-9
                else:
                    radius = 1e-9
                if path.contains_point((x, y), radius=radius):
                    return icell2d
        if forgive:
            icell2d = np.nan
            return icell2d
        raise Exception('x, y point given is outside of the model area')

    def get_cell_vertices(self, cellid):
        """
        Method to get a set of cell vertices for a single cell
            used in the Shapefile export utilities
        :param cellid: (int) cellid number
        :return: list of x,y cell vertices
        """
        self._copy_cache = False
        cell_verts = list(zip(self.xvertices[cellid],
                              self.yvertices[cellid]))
        self._copy_cache = True
        return cell_verts

    def plot(self, **kwargs):
        """
        Plot the grid lines.

        Parameters
        ----------
        kwargs : ax, colors.  The remaining kwargs are passed into the
            the LineCollection constructor.

        Returns
        -------
        lc : matplotlib.collections.LineCollection

        """
        from flopy.plot import PlotMapView

        mm = PlotMapView(modelgrid=self)
        return mm.plot_grid(**kwargs)

    def _build_grid_geometry_info(self):
        cache_index_cc = 'cellcenters'
        cache_index_vert = 'xyzgrid'

        vertexdict = {v[0]: [v[1], v[2]]
                      for v in self._vertices}
        xcenters = []
        ycenters = []
        xvertices = []
        yvertices = []

        # build xy vertex and cell center info
        for cell2d in self._cell2d:
            cell2d = tuple(cell2d)
            xcenters.append(cell2d[1])
            ycenters.append(cell2d[2])

            vert_number = []
            for i in cell2d[4:]:
                if i is not None:
                    vert_number.append(int(i))

            xcellvert = []
            ycellvert = []
            for ix in vert_number:
                xcellvert.append(vertexdict[ix][0])
                ycellvert.append(vertexdict[ix][1])
            xvertices.append(xcellvert)
            yvertices.append(ycellvert)

        # build z cell centers
        zvertices, zcenters = self._zcoords()

        if self._has_ref_coordinates:
            # transform x and y
            xcenters, ycenters = self.get_coords(xcenters, ycenters)
            xvertxform = []
            yvertxform = []
            # vertices are a list within a list
            for xcellvertices, ycellvertices in zip(xvertices, yvertices):
                xcellvertices, \
                ycellvertices = self.get_coords(xcellvertices, ycellvertices)
                xvertxform.append(xcellvertices)
                yvertxform.append(ycellvertices)
            xvertices = xvertxform
            yvertices = yvertxform

        self._cache_dict[cache_index_cc] = CachedData([xcenters,
                                                       ycenters,
                                                       zcenters])
        self._cache_dict[cache_index_vert] = CachedData([xvertices,
                                                         yvertices,
                                                         zvertices])


if __name__ == "__main__":
    import os
    import flopy as fp

    ws = "../../examples/data/mf6/test003_gwfs_disv"
    name = "mfsim.nam"

    sim = fp.mf6.modflow.MFSimulation.load(sim_name=name, sim_ws=ws)

    print(sim.model_names)
    ml = sim.get_model("gwf_1")

    dis = ml.dis

    t = VertexGrid(dis.vertices.array, dis.cell2d.array, top=dis.top.array,
                   botm=dis.botm.array, idomain=dis.idomain.array,
                   epsg=26715, xoff=0, yoff=0, angrot=45)

    sr_x = t.xvertices
    sr_y = t.yvertices
    sr_xc = t.xcellcenters
    sr_yc = t.ycellcenters
    sr_lc = t.grid_lines
    sr_e = t.extent

    t.use_ref_coords = False
    x = t.xvertices
    y = t.yvertices
    z = t.zvertices
    xc = t.xcellcenters
    yc = t.ycellcenters
    zc = t.zcellcenters
    lc = t.grid_lines
    e = t.extent
