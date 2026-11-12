// EDK 키트의 packages/common·packages/ui 를 apps/web 의 tsconfig(TS 5.6.3, 엄격한 설정)로 타입 검사에 넣는 자리.
// 어느 화면도 이 파일을 import 하지 않는다. 그래서 진입 청크에 들지 않고, tsc 만 이 파일을 거쳐 키트 파일을 읽는다.
// 이 import 를 지우면 키트 패키지가 apps/web 의 typecheck 에 한 번도 들어가지 않는다(심은 파손 (나)가 아무것도 못 잡는다).
// 부품은 들이기로 한 25 만 가져온다. button·table-empty 는 다시 만들 부품이라 가져오지 않는다(kit-imports.test.ts 가 지킨다).
import { AlertIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Icon } from '@marcspon/common/generated/icons/icon-base';
import * as Accordion from '@marcspon/ui/components/accordion';
import * as Badge from '@marcspon/ui/components/badge';
import * as Checkbox from '@marcspon/ui/components/checkbox';
import * as Dialog from '@marcspon/ui/components/dialog';
import * as DotsThreeVerticalIcon from '@marcspon/ui/components/dots-three-vertical-icon';
import * as DropdownMenu from '@marcspon/ui/components/dropdown-menu';
import * as EditIcon from '@marcspon/ui/components/edit-icon';
import * as Form from '@marcspon/ui/components/form';
import * as KitIcon from '@marcspon/ui/components/icon';
import * as Input from '@marcspon/ui/components/input';
import * as Label from '@marcspon/ui/components/label';
import * as RadioGroup from '@marcspon/ui/components/radio-group';
import * as ScrollUpButton from '@marcspon/ui/components/scroll-up-button';
import * as SearchInput from '@marcspon/ui/components/search-input';
import * as Sheet from '@marcspon/ui/components/sheet';
import * as Skeleton from '@marcspon/ui/components/skeleton';
import * as SortIndicator from '@marcspon/ui/components/sort-indicator';
import * as Spinner from '@marcspon/ui/components/spinner';
import * as Switch from '@marcspon/ui/components/switch';
import * as Table from '@marcspon/ui/components/table';
import * as TableSkeleton from '@marcspon/ui/components/table-skeleton';
import * as Tabs from '@marcspon/ui/components/tabs';
import * as Textarea from '@marcspon/ui/components/textarea';
import * as Tooltip from '@marcspon/ui/components/tooltip';
import * as XlsIcon from '@marcspon/ui/components/xls-icon';
import { cn } from '@marcspon/ui/lib/utils';

/** 들인 부품 25 의 모듈. 타입 검사에 넣으려고 이름으로 잡아 둘 뿐 쓰지 않는다. */
export const kitModules = [
  Accordion,
  Badge,
  Checkbox,
  Dialog,
  DotsThreeVerticalIcon,
  DropdownMenu,
  EditIcon,
  Form,
  KitIcon,
  Input,
  Label,
  RadioGroup,
  ScrollUpButton,
  SearchInput,
  Sheet,
  Skeleton,
  SortIndicator,
  Spinner,
  Switch,
  Table,
  TableSkeleton,
  Tabs,
  Textarea,
  Tooltip,
  XlsIcon,
] as const;

export function KitTypecheck() {
  return (
    <>
      <AlertIcon color="black-transparent.100" boxSize="16px" />
      <Icon viewBox="0 0 16 16" className={cn('twp', 'font-pretendard')} />
    </>
  );
}
