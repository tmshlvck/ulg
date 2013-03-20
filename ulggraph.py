#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# (C) 2012 CZ.NIC, z.s.p.o.
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
USED_LINE_COLOR = 'red'
RECONLY_LINE_COLOR = 'gray'
REC_LINE_COLOR = 'blue'
FONT_SIZE = 10
LABEL_FONT_SIZE = 8
REC_LINE_WIDTH = 0.5
USED_LINE_WIDTH = 1.2

def bgp_graph_gen(graphdata,start=None,end=None):
	gr = digraph()

	def transform_nodename(name):
		return name.replace(":", "")

	def transform_label(s):
		return "".join(["&#%d;"%ord(x) for x in s])

	def add_node(graph,v,fillcolor=None,shape='ellipse'):
		vid = transform_nodename(v)
		if(not graph.has_node(vid)):
			params = [('fontsize',FONT_SIZE),('shape',shape),('label',transform_label(v))]
			if(fillcolor):
				params = params + [('style','filled'),('fillcolor',fillcolor)]

			graph.add_node(vid,attrs=params)

	def add_edge(graph,v1,v2,color='black',style='solid',penwidth=REC_LINE_WIDTH,label=None):
		if(v1==v2):
			return

		vid1 = transform_nodename(v1)
		vid2 = transform_nodename(v2)

		if(not graph.has_edge((vid1,vid2))):
			params = [('color',color),('style',style),('penwidth',penwidth)]
			if(label):
				params = params + [('fontsize',LABEL_FONT_SIZE),('label',transform_label(" "+label+"  "))]

			graph.add_edge((vid1,vid2),attrs=params)



	for gd in graphdata:
		if(start):
			add_node(gr,start,shape='box',fillcolor=USED_FILL_COLOR)
			add_node(gr,gd[0][0],fillcolor=USED_FILL_COLOR)
			add_edge(gr,start,gd[0][0],color=USED_LINE_COLOR,penwidth=USED_LINE_WIDTH,style='dashed')


		vparams = {}
		eparams = {}
		if(gd[1]['recuse']):
			eparams['color']=USED_LINE_COLOR
			eparams['penwidth']=USED_LINE_WIDTH
			vparams['fillcolor']=USED_FILL_COLOR
		elif(gd[1]['reconly']):
			eparams['color']=RECONLY_LINE_COLOR
			eparams['style']='dotted'
			eparams['penwidth']=REC_LINE_WIDTH
		else:
			eparams['penwidth']=REC_LINE_WIDTH
			eparams['color']=REC_LINE_COLOR

		i = 0
		while (i < len(gd[0])):
		       	if(i+1 < len(gd[0])):
				add_node(gr,gd[0][i],**vparams)
				add_node(gr,gd[0][i+1],**vparams)

				if((i==0) and ('peer' in gd[1])):
					add_edge(gr,gd[0][i],gd[0][i+1],label=gd[1]['peer'],**eparams)
				else:
					add_edge(gr,gd[0][i],gd[0][i+1],**eparams)
			i = i+1

		if(end):
			add_node(gr,end,shape='box',fillcolor=USED_FILL_COLOR)
			add_edge(gr,gd[0][-1],end,color=USED_LINE_COLOR,penwidth=USED_LINE_WIDTH,style='dashed')

	dot = write(gr)
	gvv = gv.readstring(dot)
	gv.layout(gvv,'dot')
	gv.render(gvv,'png')
