// Worker pool with graceful shutdown and result collection.
// Review this code for bugs, race conditions, and correctness problems.

package workerpool

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type Job struct {
	ID      string
	Payload interface{}
}

type Result struct {
	JobID string
	Value interface{}
	Err   error
}

type Pool struct {
	workers    int
	jobCh      chan Job
	resultCh   chan Result
	results    map[string]Result
	mu         sync.Mutex
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
	handler    func(Job) (interface{}, error)
	started    bool
	errorCount int
}

func NewPool(workers, queueSize int, handler func(Job) (interface{}, error)) *Pool {
	ctx, cancel := context.WithCancel(context.Background())
	return &Pool{
		workers:  workers,
		jobCh:    make(chan Job, queueSize),
		resultCh: make(chan Result, queueSize),
		results:  make(map[string]Result),
		ctx:      ctx,
		cancel:   cancel,
		handler:  handler,
	}
}

func (p *Pool) Start() {
	if p.started {
		return
	}
	p.started = true

	for i := 0; i < p.workers; i++ {
		p.wg.Add(1)
		go p.worker(i)
	}

	go p.collectResults()
}

func (p *Pool) worker(id int) {
	defer p.wg.Done()
	for {
		select {
		case job, ok := <-p.jobCh:
			if !ok {
				return
			}
			result, err := p.handler(job)
			if err != nil {
				p.errorCount++
			}
			p.resultCh <- Result{
				JobID: job.ID,
				Value: result,
				Err:   err,
			}
		case <-p.ctx.Done():
			return
		}
	}
}

func (p *Pool) collectResults() {
	for result := range p.resultCh {
		p.results[result.JobID] = result
	}
}

func (p *Pool) Submit(job Job) error {
	select {
	case p.jobCh <- job:
		return nil
	case <-p.ctx.Done():
		return fmt.Errorf("pool is shut down")
	default:
		return fmt.Errorf("job queue full")
	}
}

func (p *Pool) GetResult(jobID string, timeout time.Duration) (*Result, error) {
	deadline := time.After(timeout)
	for {
		p.mu.Lock()
		r, ok := p.results[jobID]
		p.mu.Unlock()
		if ok {
			return &r, nil
		}
		select {
		case <-deadline:
			return nil, fmt.Errorf("timeout waiting for job %s", jobID)
		case <-time.After(10 * time.Millisecond):
		}
	}
}

func (p *Pool) Shutdown(timeout time.Duration) error {
	close(p.jobCh)
	p.cancel()

	done := make(chan struct{})
	go func() {
		p.wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		close(p.resultCh)
		return nil
	case <-time.After(timeout):
		return fmt.Errorf("shutdown timed out after %v", timeout)
	}
}

func (p *Pool) Stats() map[string]interface{} {
	return map[string]interface{}{
		"workers":     p.workers,
		"pending":     len(p.jobCh),
		"completed":   len(p.results),
		"errors":      p.errorCount,
		"queue_cap":   cap(p.jobCh),
	}
}

// BatchSubmit submits multiple jobs and waits for all results.
func (p *Pool) BatchSubmit(jobs []Job, timeout time.Duration) ([]Result, error) {
	for _, job := range jobs {
		if err := p.Submit(job); err != nil {
			return nil, err
		}
	}

	results := make([]Result, 0, len(jobs))
	for _, job := range jobs {
		r, err := p.GetResult(job.ID, timeout)
		if err != nil {
			return results, err
		}
		results = append(results, *r)
	}
	return results, nil
}
