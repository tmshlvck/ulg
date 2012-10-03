#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# by Tomas Hlavacek (tomas.hlavacek@nic.cz)
# last udate: June 21 2012
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Imports
import defaults

import gv
from pygraph.classes.digraph import digraph
from pygraph.readwrite.dot import write

USED_FILL_COLOR = '#DC738A'
FONT_SIZE = 10
LABEL_FONT_SIZE = 8

def bgp_graph_gen(graphdata,start=None,end=None):
	gr = digraph()

	def add_edge(graph,v1,v2,color='black',style='solid',penwidth=1.0,fillcolor=None,label=None):
		params = [('fontsize',FONT_SIZE)]
		if(fillcolor):
			params = params + [('style','filled'),('fillcolor',fillcolor)]

		if(not graph.has_node(v1)):
			graph.add_node(v1,attrs=params)
		if(not graph.has_node(v2)):
			graph.add_node(v2,attrs=params)

		if(v1==v2):
			return

		eparams = [('color',color),('style',style),('penwidth',penwidth)]
		if(label):
			eparams = eparams + [('fontsize',LABEL_FONT_SIZE),('label',' '+label+'  ')]

		if(not graph.has_edge((v1,v2))):
		       	graph.add_edge((v1,v2),attrs=eparams)

	for gd in graphdata:
		params = {}
		if(gd[1]['recuse']):
			params['color']='red'
			params['penwidth']=1.2
			params['fillcolor']=USED_FILL_COLOR
		elif(gd[1]['reconly']):
			params['color']='gray'
			params['style']='dotted'
			params['penwidth']=0.5
		else:
			params['penwidth']=0.5
			params['color']='blue'

		if(start):
			if(not gr.has_node(start)):
				gr.add_node(start,attrs=[('shape','box'),('style','filled'),('fillcolor',USED_FILL_COLOR),('fontsize',FONT_SIZE)])
			add_edge(gr,start,gd[0][0],**{'color':'red','penwidth':1.2,'style':'dashed','fillcolor':USED_FILL_COLOR})

		i = 0
		while (i < len(gd[0])):
		       	if(i+1 < len(gd[0])):
				if((i==0) and ('peer' in gd[1])):
					add_edge(gr,gd[0][i],gd[0][i+1],label=gd[1]['peer'],**params)
				else:
					add_edge(gr,gd[0][i],gd[0][i+1],**params)
			i = i+1

		if(not gr.has_node(end)):
			gr.add_node(end,attrs=[('shape','box'),('style','filled'),('fillcolor',USED_FILL_COLOR),('fontsize',FONT_SIZE)])
		add_edge(gr,gd[0][-1],end,**{'color':'red','penwidth':1.2,'style':'dashed'})

	dot = write(gr)
	gvv = gv.readstring(dot)
	gv.layout(gvv,'dot')
	gv.render(gvv,'png')
