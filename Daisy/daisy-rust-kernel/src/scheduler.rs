#![allow(dead_code)]
use alloc::collections::VecDeque;

const NUM_PRIORITIES: usize = 10;

pub struct Scheduler {
    queues: [VecDeque<u64>; NUM_PRIORITIES],
    current: Option<u64>,
}

impl Default for Scheduler {
    fn default() -> Self { Self::new() }
}

impl Scheduler {
    pub fn new() -> Self {
        Self {
            queues: core::array::from_fn(|_| VecDeque::new()),
            current: None,
        }
    }

    pub fn add(&mut self, task_id: u64, priority: u8) {
        let p = (priority as usize).min(NUM_PRIORITIES - 1);
        if !self.queues[p].contains(&task_id) {
            self.queues[p].push_back(task_id);
        }
    }

    pub fn remove(&mut self, task_id: u64) {
        for q in self.queues.iter_mut() {
            q.retain(|&id| id != task_id);
        }
        if self.current == Some(task_id) {
            self.current = None;
        }
    }

    #[inline]
    pub fn next(&mut self) -> Option<u64> {
        for q in self.queues.iter_mut() {
            if let Some(id) = q.pop_front() {
                q.push_back(id);
                self.current = Some(id);
                return Some(id);
            }
        }
        None
    }

    #[inline]
    pub fn yield_current(&mut self) {}

    #[inline]
    pub fn current_task(&self) -> Option<u64> {
        self.current
    }
}
