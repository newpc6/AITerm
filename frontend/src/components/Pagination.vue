<template>
  <div class="pagination-wrapper">
    <el-pagination v-model:current-page="currentPage" v-model:page-size="currentPageSize" :page-sizes="pageSizeOptions"
      :total="total" :background="true" layout="total, prev, pager, next, sizes" @current-change="handlePageChange"
      @size-change="handleSizeChange" />
  </div>
</template>

<script lang="ts">
import { defineComponent, computed, PropType } from "vue";

export default defineComponent({
  name: "Pagination",
  props: {
    page: {
      type: Number as PropType<number>,
      required: true,
    },
    pageSize: {
      type: Number as PropType<number>,
      default: 10,
    },
    total: {
      type: Number as PropType<number>,
      required: true,
    },
    pageSizeOptions: {
      type: Array as PropType<number[]>,
      default: () => [10, 20, 30, 50],
    },
  },
  emits: ["update:page", "update:pageSize", "change", "sizeChange"],
  setup(props, { emit }) {
    const currentPage = computed({
      get: () => props.page,
      set: (val) => emit("update:page", val),
    });

    const currentPageSize = computed({
      get: () => props.pageSize,
      set: (val) => emit("update:pageSize", val),
    });

    const handlePageChange = (page: number) => {
      emit("change", page);
    };

    const handleSizeChange = (size: number) => {
      emit("sizeChange", size);
    };

    return {
      currentPage,
      currentPageSize,
      handlePageChange,
      handleSizeChange,
    };
  },
});
</script>

<style scoped>
.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: 12px 0;
}

.pagination-wrapper :deep(.el-pagination) {
  --el-pagination-bg-color: #2d2d2d;
  --el-pagination-text-color: #e0e0e0;
  --el-pagination-button-disabled-bg-color: #2d2d2d;
  --el-pagination-button-disabled-color: #666;
  --el-pagination-hover-color: #409eff;
}

.pagination-wrapper :deep(.el-pagination .el-pager li) {
  background-color: #2d2d2d;
  color: #e0e0e0;
}

.pagination-wrapper :deep(.el-pagination .el-pager li:hover) {
  color: #409eff;
}

.pagination-wrapper :deep(.el-pagination .el-pager li.is-active) {
  background-color: #409eff;
  color: #fff;
}

.pagination-wrapper :deep(.el-pagination button) {
  background-color: #2d2d2d;
  color: #e0e0e0;
}

.pagination-wrapper :deep(.el-pagination button:hover) {
  color: #409eff;
}

.pagination-wrapper :deep(.el-pagination button:disabled) {
  background-color: #2d2d2d;
  color: #666;
}

.pagination-wrapper :deep(.el-pagination .el-pagination__total),
.pagination-wrapper :deep(.el-pagination .el-pagination__sizes) {
  color: #999;
}

.pagination-wrapper :deep(.el-pagination .el-select .el-input__wrapper) {
  background-color: #2d2d2d;
  box-shadow: 0 0 0 1px #404040 inset;
}

.pagination-wrapper :deep(.el-pagination .el-select .el-input__inner) {
  color: #e0e0e0;
}
</style>
