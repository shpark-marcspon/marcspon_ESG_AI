// 변경에 성공하면 조회를 무효로 표시하는 훅. 모양을 모른다.
//
// 쓰는 법:  const useChange = createInvalidatingMutation(api);   // 모듈 맨 위나 한 번만
//           const create = useChange("post", "/sites");           // 컴포넌트 안에서. $api.useMutation 과 같은 꼴이다
// 변경이 실패하면 무효화하지 않는다(onSuccess 에만 건다). 무효화는 기다린다: 변경의 isPending 이 풀릴 때 조회는 이미 다시 받은 뒤다.
import { useQueryClient } from '@tanstack/react-query';

import type { Api } from '../client.ts';
import { INVALIDATE_AFTER_MUTATION } from '../model/index.ts';

export function createInvalidatingMutation(
  api: Api,
): Api['$api']['useMutation'] {
  return function useInvalidatingMutation(method, url, options, queryClient) {
    const client = useQueryClient(queryClient);
    return api.$api.useMutation(
      method,
      url,
      {
        ...options,
        onSuccess: async (...args) => {
          await client.invalidateQueries({
            queryKey: INVALIDATE_AFTER_MUTATION,
          });
          return options?.onSuccess?.(...args);
        },
      },
      queryClient,
    );
  };
}
