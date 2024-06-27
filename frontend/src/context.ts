import {createContext} from '@lit/context';
import {SideBarState} from './utils/enums';
export const chartSideBarStateContext = createContext<SideBarState>(
  Symbol('chartSideBarState')
);
