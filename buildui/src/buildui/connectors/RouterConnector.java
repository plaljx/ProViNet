package buildui.connectors;
/*
 * Copyright (c) 2002-2006 University of Utah and the Flux Group.
 * All rights reserved.
 * This file is part of the Emulab network testbed software.
 * 
 * Emulab is free software, also known as "open source;" you can
 * redistribute it and/or modify it under the terms of the GNU Affero
 * General Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later version.
 * 
 * Emulab is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
 * more details, which can be found in the file AGPL-COPYING at the root of
 * the source tree.
 * 
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import buildui.devices.Device;
import buildui.paint.NetElement;

import buildui.paint.PropertiesArea;
import org.w3c.dom.Element;

public class RouterConnector extends Connector {

  static int num = 1;

  public RouterConnector (String newName) {
    super(newName, "/icons/router.png");
  }

  public NetElement createAnother () {
    return new RouterConnector("router"+(num++)) ;
  }

  static PropertiesArea propertiesArea = new RouterPropertiesArea() ;

  public PropertiesArea getPropertiesArea() {
    return propertiesArea ;
  }

  @Override
  public Connection createConnection (Device dev) {
    return new EmulatedConnection("", this, dev);
  }

  @Override
  public void writeAttributes(Element xml) {
    super.writeAttributes(xml);
    xml.setAttribute("type", "router");
  }

  public void readAttributes (Element xml) {
    super.readAttributes(xml);
  }

  public static Connector readFrom (Element x_con) {
    String name = x_con.getAttribute("id") ;
    RouterConnector con = new RouterConnector(name);
    con.readAttributes(x_con);
    return con ;
  }

}