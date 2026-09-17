package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cyberrag.entity.Conversation;
import com.cyberrag.entity.Document;
import com.cyberrag.entity.KnowledgeBase;
import com.cyberrag.entity.QaRecord;
import com.cyberrag.entity.User;
import com.cyberrag.mapper.ConversationMapper;
import com.cyberrag.mapper.DocumentMapper;
import com.cyberrag.mapper.KnowledgeBaseMapper;
import com.cyberrag.mapper.QaRecordMapper;
import com.cyberrag.mapper.UserMapper;
import com.cyberrag.service.StatsService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 统计服务实现: 全部基于 MySQL 聚合查询。
 */
@Service
@RequiredArgsConstructor
public class StatsServiceImpl implements StatsService {

    private final KnowledgeBaseMapper kbMapper;
    private final DocumentMapper documentMapper;
    private final QaRecordMapper qaRecordMapper;
    private final UserMapper userMapper;
    private final ConversationMapper conversationMapper;

    @Override
    public Map<String, Object> overview() {
        LocalDate today = LocalDate.now();
        LocalDateTime todayStart = today.atStartOfDay();
        Map<String, Object> data = new HashMap<>();
        data.put("kbCount", kbMapper.selectCount(null));
        data.put("documentCount", documentMapper.selectCount(null));
        data.put("chunkCount", kbMapper.selectList(null).stream()
                .mapToInt(kb -> kb.getChunkCount() == null ? 0 : kb.getChunkCount())
                .sum());
        data.put("qaCount", qaRecordMapper.selectCount(null));
        data.put("userCount", userMapper.selectCount(null));
        data.put("conversationCount", conversationMapper.selectCount(null));
        data.put("todayQaCount", qaRecordMapper.selectCount(new LambdaQueryWrapper<QaRecord>()
                .ge(QaRecord::getCreatedAt, todayStart)));
        data.put("todayUserCount", userMapper.selectCount(new LambdaQueryWrapper<User>()
                .ge(User::getCreatedAt, todayStart)));
        return data;
    }

    @Override
    public List<Map<String, Object>> qaTrend(int days) {
        LocalDateTime start = LocalDate.now().minusDays(days - 1).atStartOfDay();
        List<QaRecord> records = qaRecordMapper.selectList(new LambdaQueryWrapper<QaRecord>()
                .ge(QaRecord::getCreatedAt, start)
                .select(QaRecord::getCreatedAt, QaRecord::getId));
        Map<String, Integer> byDay = new HashMap<>();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("MM-dd");
        for (QaRecord r : records) {
            String day = r.getCreatedAt().toLocalDate().format(fmt);
            byDay.merge(day, 1, Integer::sum);
        }
        List<Map<String, Object>> trend = new ArrayList<>();
        for (int i = days - 1; i >= 0; i--) {
            String day = LocalDate.now().minusDays(i).format(fmt);
            Map<String, Object> point = new HashMap<>();
            point.put("date", day);
            point.put("count", byDay.getOrDefault(day, 0));
            trend.add(point);
        }
        return trend;
    }

    @Override
    public List<Map<String, Object>> hotCategories(int limit) {
        // 按知识库分类聚合问答量
        List<KnowledgeBase> kbs = kbMapper.selectList(null);
        Map<Long, String> kbNames = new HashMap<>();
        Map<Long, String> kbCategories = new HashMap<>();
        for (KnowledgeBase kb : kbs) {
            kbNames.put(kb.getId(), kb.getName());
            kbCategories.put(kb.getId(), kb.getCategory() == null ? "未分类" : kb.getCategory());
        }
        List<QaRecord> records = qaRecordMapper.selectList(new LambdaQueryWrapper<QaRecord>()
                .select(QaRecord::getKnowledgeBaseId));
        Map<String, Integer> byCategory = new HashMap<>();
        for (QaRecord r : records) {
            if (r.getKnowledgeBaseId() == null) {
                continue;
            }
            String category = kbCategories.getOrDefault(r.getKnowledgeBaseId(), "其他");
            byCategory.merge(category, 1, Integer::sum);
        }
        return byCategory.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .limit(limit)
                .map(e -> Map.<String, Object>of("category", e.getKey(), "count", e.getValue()))
                .toList();
    }

    @Override
    public List<Map<String, Object>> kbUsage(int limit) {
        List<KnowledgeBase> kbs = kbMapper.selectList(null);
        List<QaRecord> records = qaRecordMapper.selectList(new LambdaQueryWrapper<QaRecord>()
                .select(QaRecord::getKnowledgeBaseId));
        Map<Long, Integer> byKb = new HashMap<>();
        for (QaRecord r : records) {
            if (r.getKnowledgeBaseId() != null) {
                byKb.merge(r.getKnowledgeBaseId(), 1, Integer::sum);
            }
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (KnowledgeBase kb : kbs) {
            Map<String, Object> item = new HashMap<>();
            item.put("name", kb.getName());
            item.put("value", byKb.getOrDefault(kb.getId(), 0));
            result.add(item);
        }
        result.sort((a, b) -> ((int) b.get("value")) - ((int) a.get("value")));
        return result.stream().limit(limit).toList();
    }

    @Override
    public List<Map<String, Object>> recentQa(int limit) {
        List<QaRecord> records = qaRecordMapper.selectList(new LambdaQueryWrapper<QaRecord>()
                .orderByDesc(QaRecord::getCreatedAt)
                .last("LIMIT " + Math.max(1, Math.min(limit, 50))));
        return records.stream().map(r -> {
            Map<String, Object> item = new HashMap<>();
            item.put("id", r.getId());
            item.put("question", r.getQuestion());
            item.put("answer", r.getAnswer() == null ? "" :
                    r.getAnswer().substring(0, Math.min(120, r.getAnswer().length())));
            item.put("knowledgeBaseId", r.getKnowledgeBaseId());
            item.put("totalTime", r.getTotalTime());
            item.put("createdAt", r.getCreatedAt().toString());
            return item;
        }).toList();
    }
}
